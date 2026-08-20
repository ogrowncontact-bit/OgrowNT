"""packages/portfolio/manager.py — "PROMPT 8" §12-17: the Portfolio
Manager's per-strategy allocation cap, a genuinely separate check from
Risk Engine's per-asset/correlation-cluster caps (see that module's
docstring). Uses the real config/risk_limits.yaml (max_strategy_allocation_pct
= 30), same "test against the real limits, not a hand-rolled stand-in"
discipline as tests/test_risk_simulation.py.
"""
from datetime import datetime, timezone

from packages.portfolio.manager import evaluate_allocation
from packages.portfolio.state import PortfolioState
from packages.risk.config import load_risk_limits
from packages.shared.models import Position

LIMITS = load_risk_limits()
NOW = datetime.now(timezone.utc)


def _state(open_positions: list[Position], equity: float = 10_000.0) -> PortfolioState:
    return PortfolioState(
        ts=NOW, cash=equity, equity=equity, exposure_pct=0.0, daily_pnl=0.0, daily_loss_pct=0.0,
        weekly_pnl=0.0, weekly_loss_pct=0.0, monthly_pnl=0.0, monthly_loss_pct=0.0,
        drawdown_pct=0.0, unrealized_pnl=0.0, open_positions=open_positions,
    )


def _position(strategy_id: int, entry_price: float, size: float) -> Position:
    # Never committed to the DB — evaluate_allocation only ever reads plain
    # attributes off these, so an in-memory instance is enough.
    return Position(
        asset_id=1, strategy_id=strategy_id, direction="long", entry_price=entry_price,
        current_stop=entry_price * 0.95, size=size, status="open",
    )


def test_approves_when_strategy_has_no_existing_exposure():
    decision = evaluate_allocation(strategy_id=1, candidate_notional_pct=10.0, portfolio_state=_state([]), limits=LIMITS)
    assert decision.approved
    assert decision.reason == "approved"
    assert decision.strategy_allocation_pct == 0.0
    assert decision.approved_notional_pct == 10.0


def test_blocks_when_strategy_already_at_the_cap():
    # 100 * 30 = 3000 notional on 10000 equity = 30% == max_strategy_allocation_pct exactly.
    existing = [_position(strategy_id=1, entry_price=100.0, size=30.0)]
    decision = evaluate_allocation(strategy_id=1, candidate_notional_pct=5.0, portfolio_state=_state(existing), limits=LIMITS)
    assert not decision.approved
    assert decision.reason == "strategy_allocation_exceeded"
    assert decision.approved_notional_pct == 0.0


def test_caps_the_candidate_to_remaining_headroom_instead_of_rejecting_outright():
    # 100 * 25 = 2500 notional = 25% -> 5% headroom left before the 30% cap.
    existing = [_position(strategy_id=1, entry_price=100.0, size=25.0)]
    decision = evaluate_allocation(strategy_id=1, candidate_notional_pct=10.0, portfolio_state=_state(existing), limits=LIMITS)
    assert decision.approved
    assert decision.reason == "approved_capped"
    assert decision.approved_notional_pct == 5.0
    assert decision.strategy_allocation_pct == 25.0


def test_a_different_strategys_exposure_never_counts_against_this_one():
    existing = [_position(strategy_id=2, entry_price=100.0, size=100.0)]  # strategy 2, way over any cap
    decision = evaluate_allocation(strategy_id=1, candidate_notional_pct=10.0, portfolio_state=_state(existing), limits=LIMITS)
    assert decision.approved
    assert decision.reason == "approved"
    assert decision.strategy_allocation_pct == 0.0


def test_invalid_equity_is_rejected_not_divided_by_zero():
    decision = evaluate_allocation(strategy_id=1, candidate_notional_pct=10.0, portfolio_state=_state([], equity=0.0), limits=LIMITS)
    assert not decision.approved
    assert decision.reason == "invalid_input"
