"""ExecutionGate — "PROMPT 13" §5-6, §14-19, §65-66, §71-72.

The final revalidation immediately before an order reaches
order_manager.py's open_position()/close_position()/reduce_position() —
Risk Engine and Portfolio Manager approvals already happened
(apps/worker/risk_execution.py::maybe_execute), but §15's own reasoning
("market conditions may have changed") means that approval can be seconds
to minutes stale by the time a real submit actually happens. This module
re-checks the handful of things that could have genuinely changed in that
window, plus two checks nothing upstream performs at all:
  - net execution expectancy (§65-66) — wires packages/risk/costs.py's
    evaluate_net_expectancy(), built in "PROMPT 12" but deliberately left
    unwired pending exactly this module (see that file's own docstring).
  - instrument precision (§61-62) — packages/execution/instrument.py,
    genuinely new this phase.

§72's ExecutionApproval is a plain dataclass, not a persisted table — see
packages/shared/models.py's "PROMPT 13" section comment for why.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.execution.broker.base import BrokerAdapter
from packages.execution.firewall import LiveTradingDisabledError, LiveTradingFirewall
from packages.execution.instrument import get_instrument, validate_precision
from packages.market.sessions import SESSION_CLOSED, MarketSessionEngine
from packages.risk.costs import estimate_round_trip_cost, evaluate_net_expectancy
from packages.shared.market_data import get_latest_candle_row
from packages.shared.models import Asset, Signal, StrategyPerformance, SystemState

# §17 — a fixed engineering tolerance for this synchronous, single-tick
# paper system, not a risk_limits.yaml-tunable number: this is a sanity
# bound on "did the price move enough since the signal was scored that
# resubmitting blind would be a mistake," not a portfolio-level risk limit
# (which is what risk_limits.yaml is reserved for).
MAX_PRICE_DEVIATION_PCT = 1.0

# §72 — how long THIS approval itself may be trusted before a caller must
# re-run evaluate() rather than reuse a stale ExecutionApproval.
EXECUTION_APPROVAL_TTL_SECONDS = 30


def _latest_expectancy(db: Session, strategy_id: int) -> float | None:
    row = (
        db.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy_id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )
    return row.expectancy if row is not None else None


@dataclass(frozen=True)
class ExecutionApproval:
    approved: bool
    reason: str
    checks: list[str] = field(default_factory=list)
    expires_at: datetime | None = None


def evaluate(
    db: Session,
    *,
    signal_row: Signal,
    asset: Asset,
    direction: str,
    entry_price: float,
    stop_price: float,
    quantity: float,
    system_state: SystemState,
    broker: BrokerAdapter | None = None,
    now: datetime | None = None,
) -> ExecutionApproval:
    now = now or datetime.now(timezone.utc)
    checks: list[str] = []

    # §2, §97 — checked first, unconditionally: even a perfectly-formed
    # paper order never bypasses the firewall.
    try:
        LiveTradingFirewall.check(system_state.trading_mode or "paper")
        checks.append("live_trading_firewall:ok")
    except LiveTradingDisabledError as exc:
        return ExecutionApproval(approved=False, reason=f"live_trading_blocked: {exc}", checks=checks)

    # §16 — a signal minted many cycles ago (Prompt 11's opportunity_type
    # decay) should not still be tradeable.
    if signal_row.expires_at is not None and now > signal_row.expires_at:
        checks.append("signal_expiration:failed")
        return ExecutionApproval(approved=False, reason="signal_expired", checks=checks)
    checks.append("signal_expiration:ok")

    if quantity <= 0:
        checks.append("position_size:failed")
        return ExecutionApproval(approved=False, reason="invalid_position_size", checks=checks)
    checks.append("position_size:ok")

    # §19 — market status: an asset whose session has since closed (forex
    # weekend, an exchange's trading hours) can't be traded even though the
    # signal itself is still fresh.
    session = MarketSessionEngine().state_for(asset.asset_class, asset.exchange, now)
    if session.state == SESSION_CLOSED:
        checks.append("market_status:failed")
        return ExecutionApproval(approved=False, reason="market_closed", checks=checks)
    checks.append("market_status:ok")

    # §46, §67 — broker availability, when a specific adapter is supplied.
    if broker is not None:
        health = broker.health_check()
        if not health.ok:
            checks.append("broker_health:failed")
            return ExecutionApproval(approved=False, reason="broker_unavailable", checks=checks)
        checks.append("broker_health:ok")

    candle = get_latest_candle_row(db, asset.id)
    if candle is None or candle.data_quality != "high":
        checks.append("data_conflict:failed")
        return ExecutionApproval(approved=False, reason="data_unavailable", checks=checks)
    checks.append("data_conflict:ok")

    # §17 — how far has price moved since the signal was scored.
    deviation_pct = abs(candle.close - entry_price) / entry_price * 100 if entry_price > 0 else 0.0
    if deviation_pct > MAX_PRICE_DEVIATION_PCT:
        checks.append("price_deviation:failed")
        return ExecutionApproval(
            approved=False, reason=f"price_deviation_exceeded ({deviation_pct:.3f}% > {MAX_PRICE_DEVIATION_PCT}%)", checks=checks,
        )
    checks.append("price_deviation:ok")

    # §61-62 — instrument precision (tick/step/min quantity/min notional).
    instrument = get_instrument(asset)
    precision = validate_precision(quantity=quantity, price=candle.close, instrument=instrument)
    if not precision.ok:
        checks.append("instrument_precision:failed")
        return ExecutionApproval(approved=False, reason=f"precision_violation: {'; '.join(precision.violations)}", checks=checks)
    checks.append("instrument_precision:ok")

    # §65-66 — net expectancy after real transaction costs (reuses "PROMPT
    # 12"'s packages/risk/costs.py, left deliberately unwired until this
    # module existed).
    expectancy_r = _latest_expectancy(db, signal_row.strategy_id)
    cost = estimate_round_trip_cost(mid_price=candle.close, volume=candle.volume, qty=quantity, direction=direction)
    risk_amount = abs(entry_price - stop_price) * quantity
    net_expectancy = evaluate_net_expectancy(expectancy_r=expectancy_r, risk_amount=risk_amount, cost=cost)
    if net_expectancy.evaluated and not net_expectancy.passes:
        checks.append("net_expectancy:failed")
        return ExecutionApproval(
            approved=False,
            reason=f"negative_net_expectancy (net_expected_edge={net_expectancy.net_expected_edge})",
            checks=checks,
        )
    checks.append("net_expectancy:ok" if net_expectancy.evaluated else "net_expectancy:not_evaluated")

    return ExecutionApproval(
        approved=True, reason="approved", checks=checks,
        expires_at=now + timedelta(seconds=EXECUTION_APPROVAL_TTL_SECONDS),
    )
