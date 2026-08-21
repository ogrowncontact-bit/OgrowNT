"""End-to-end scenarios -- "PROMPT 13" §107-111. Each scenario exercises the
FULL pipeline (or as much of it as the scenario's own spec §-range calls
for), not an isolated unit -- complementing tests/test_execution_red_team.py
(structural/static proofs) and tests/test_execution_chaos.py (isolated
failure-mode proofs) with genuine multi-layer, multi-call proofs that the
layers actually compose the way the spec claims they do.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import apps.worker.risk_execution as risk_execution
from apps.worker.risk_execution import maybe_execute
from packages.agents import chief as chief_decision
from packages.agents.context import AgentContext
from packages.agents.orchestrator import run_agent_cycle
from packages.data.connectors.market.base import Candle
from packages.data.quality import compute_quality_score
from packages.execution.adapters.base import OrderRequest, OrderResult
from packages.execution.broker.base import AccountInfo
from packages.execution.broker.paper import PaperBrokerAdapter
from packages.execution.broker.registry import get_or_create_broker_row
from packages.execution.broker_reconciliation import run_broker_reconciliation_and_enforce
from packages.execution.order_manager import open_position
from packages.quant.indicators.core import IndicatorSet, compute_indicators
from packages.quant.regime.classifier import RegimeResult, classify_regime
from packages.quant.scoring.engine import OpportunityScore as ScoreResult
from packages.quant.strategies import ALL_STRATEGIES
from packages.quant.strategies.base import AnalysisResult, MarketContext, StrategySignal
from packages.shared.models import OHLCV, Asset, Execution, Order, Position, Signal, StrategyRow, SystemState, TradingEvent

_STRATEGY = ALL_STRATEGIES[0]
_NOW = datetime.now(timezone.utc)


def _asset(db_session, symbol: str, *, asset_class: str = "crypto") -> Asset:
    asset = Asset(symbol=symbol, asset_class=asset_class, is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _asset_with_price(db_session, symbol: str, price: float, *, volume: float = 1000.0) -> Asset:
    asset = _asset(db_session, symbol)
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=volume, data_quality="high")
    )
    db_session.commit()
    return asset


def _strategy_row(db_session, code: str) -> StrategyRow:
    row = StrategyRow(code=code, name=code, family=_STRATEGY.family, version="1.0")
    db_session.add(row)
    db_session.commit()
    return row


def _signal(db_session, asset: Asset, strategy_row: StrategyRow, *, entry_price: float = 100.0, expires_at: datetime | None = None) -> Signal:
    signal = Signal(
        strategy_id=strategy_row.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long",
        entry_price=entry_price, stop_price=entry_price * 0.95, target_price=entry_price * 1.15,
        status="approved", expires_at=expires_at,
    )
    db_session.add(signal)
    db_session.commit()
    return signal


def _maybe_execute_kwargs(db_session, asset: Asset, strategy_row: StrategyRow, *, entry_price: float = 100.0) -> dict:
    """Same construction as tests/test_agent_worker_wiring.py's own helper --
    a real OHLCV row is required because PaperBrokerAdapter (like
    PaperExecutionProvider before it) fills from packages/shared/
    market_data.py::get_latest_candle_row, not from the in-memory
    MarketContext."""
    now = datetime.now(timezone.utc)
    candles = [
        Candle(ts=now - timedelta(minutes=5 - i), open=entry_price, high=entry_price * 1.001, low=entry_price * 0.999, close=entry_price, volume=1000, data_quality="high")
        for i in range(5)
    ]
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=now, open=entry_price, high=entry_price * 1.001, low=entry_price * 0.999, close=entry_price, volume=1000, data_quality="high")
    )
    db_session.commit()
    indicators = IndicatorSet(
        close=entry_price, sma_fast=entry_price, sma_slow=entry_price, ema_fast=entry_price, ema_slow=entry_price,
        rsi_14=50.0, atr_14=entry_price * 0.01, realized_vol_20=0.01, trend_strength=0.5, roc_10=0.0,
        avg_volume_20=1000.0, recent_high_20=entry_price, recent_low_20=entry_price,
    )
    regime = RegimeResult(regime="trending_bull", confidence=0.8, features={})
    ctx = MarketContext(asset_id=asset.id, symbol=asset.symbol, timeframe="1m", candles=candles, indicators=indicators, regime=regime)
    analysis = AnalysisResult(direction="long", strength=0.9, rationale={})
    signal = StrategySignal(direction="long", entry_price=entry_price, stop_price=entry_price * 0.95, target_price=entry_price * 1.15, strength=0.9, rationale={})

    signal_row = Signal(
        strategy_id=strategy_row.id, asset_id=asset.id, ts=now, direction="long",
        entry_price=signal.entry_price, stop_price=signal.stop_price, target_price=signal.target_price, status="scored",
    )
    db_session.add(signal_row)
    db_session.commit()

    score = ScoreResult(
        technical=80.0, pattern=0.0, regime_fit=80.0, historical_edge=50.0, liquidity=80.0, news=50.0,
        risk_reward=80.0, strategy_performance=50.0, volatility_penalty_points=0.0, correlation_penalty_points=0.0,
        execution_cost_penalty_points=0.0, drawdown_penalty_points=0.0, final_score=85.0, tier="high_quality",
    )
    return dict(ctx=ctx, asset=asset, strategy=_STRATEGY, analysis=analysis, signal=signal, signal_row=signal_row, score=score)


# -- Scenario A (§107) -- full paper pipeline, executed, reconciles clean --
def test_scenario_a_full_paper_pipeline_executes_and_reconciles_cleanly(db_session):
    asset = _asset(db_session, "E2ESCENARIOA")
    strategy_row = _strategy_row(db_session, "e2e_scenario_a_strategy")
    kwargs = _maybe_execute_kwargs(db_session, asset, strategy_row)

    broker_row = get_or_create_broker_row(db_session, name="paper", kind="paper")
    db_session.commit()
    adapter = PaperBrokerAdapter(db_session)

    outcome = maybe_execute(db_session, adapter, decision=None, **kwargs)
    assert outcome == "executed"

    position = db_session.query(Position).one()
    assert position.status == "open"
    order = db_session.query(Order).filter(Order.position_id == position.id).one()
    assert order.status == "filled"
    execution = db_session.query(Execution).filter(Execution.order_id == order.id).one()
    assert execution.quantity == position.size
    assert execution.execution_mode == "paper"

    # §33-38, §78 -- broker-level reconciliation immediately afterward finds
    # the freshly-opened position/order/account state consistent.
    # PaperBrokerAdapter's own view is derived from these SAME tables, so
    # this reconciles "clean by construction" -- see
    # packages/execution/broker_reconciliation.py's module docstring.
    result = run_broker_reconciliation_and_enforce(db_session, adapter, broker_id=broker_row.id)
    assert result.ok is True
    state = db_session.get(SystemState, True)
    assert state.trading_paused is False


# -- Scenario B (§108) -- broker network failure -> UNKNOWN -> continue safely --
class _NetworkFailureAdapter:
    """§100/§108 -- the request reaches the broker, but the response is lost
    to a network failure mid-call. A real broker client typically surfaces
    this as an ambiguous outcome, not a raised exception (contrast with
    tests/test_execution_chaos.py's _OutageAdapter, where the call never
    even leaves this process) -- so this stub honestly reports
    status="unknown" rather than fabricating either a fill or a rejection."""

    kind = "paper"
    is_paper = True

    def __init__(self) -> None:
        self.queried_after_unknown = False

    def submit_order(self, order: OrderRequest) -> OrderResult:
        return OrderResult(broker_order_id="net-failure-order", status="unknown", detail={"reason": "network_failure_ambiguous_outcome"})

    def get_order(self, broker_order_id: str) -> OrderResult | None:
        self.queried_after_unknown = True
        return None  # the broker itself has no record either -- genuinely unknown, never silently resolved


def test_scenario_b_broker_network_failure_yields_unknown_and_the_system_continues_safely(db_session):
    asset = _asset(db_session, "E2ESCENARIOB")
    strategy_row = _strategy_row(db_session, "e2e_scenario_b_strategy")
    signal = _signal(db_session, asset, strategy_row)

    adapter = _NetworkFailureAdapter()
    position = open_position(db_session, adapter, signal=signal, asset=asset, quantity=1.0)

    # §11 -- "se broker retornar estado desconhecido: UNKNOWN. Nunca assumir
    # FILLED." No Position is fabricated, and the Order row honestly
    # persists the unknown state rather than being coerced into 'rejected'.
    assert position is None
    order = db_session.query(Order).filter(Order.signal_id == signal.id).one()
    assert order.status == "unknown"
    assert order.status != "filled"

    # "Query broker" -- the actual reconcile step -- doesn't crash even
    # though the broker itself has no record of the order either.
    queried = adapter.get_order(order.broker_order_id)
    assert queried is None
    assert adapter.queried_after_unknown is True

    # The system continues safely: an unrelated signal, on a healthy
    # broker, still executes normally right afterward -- the UNKNOWN order
    # above never corrupted any shared state.
    asset2 = _asset_with_price(db_session, "E2ESCENARIOB2", 100.0)
    strategy_row2 = _strategy_row(db_session, "e2e_scenario_b_strategy_2")
    signal2 = _signal(db_session, asset2, strategy_row2)
    healthy_adapter = PaperBrokerAdapter(db_session)
    position2 = open_position(db_session, healthy_adapter, signal=signal2, asset=asset2, quantity=1.0)
    assert position2 is not None


# -- Scenario C (§109) -- reconciliation mismatch -> BLOCK_NEW_TRADES, tied to a real subsequent rejection --
class _MismatchedAccountAdapter:
    """A broker reporting equity wildly different from this system's own
    internal ledger -- same shape as test_execution_red_team.py's own
    _MismatchedStub, reused here to prove the mismatch actually propagates
    all the way to a real signal being blocked, not just to a standalone
    BrokerReconciliationResult."""

    name = "stub_mismatch"

    def get_account(self) -> AccountInfo:
        return AccountInfo(balance=1.0, available_balance=1.0, equity=99_999_999.0, margin=0.0, margin_used=0.0, margin_available=1.0, currency="USD", ts=_NOW)

    def get_positions(self):
        return []

    def get_open_orders(self):
        return []


def test_scenario_c_reconciliation_mismatch_blocks_a_subsequent_signal_end_to_end(db_session):
    broker_row = get_or_create_broker_row(db_session, name="stub_mismatch", kind="paper")
    db_session.commit()
    result = run_broker_reconciliation_and_enforce(db_session, _MismatchedAccountAdapter(), broker_id=broker_row.id)
    assert result.ok is False

    state = db_session.get(SystemState, True)
    assert state.trading_paused is True
    assert state.trading_enabled is True  # an accounting-integrity stop, never the sovereign Kill Switch

    # A brand-new signal, run through the FULL maybe_execute() pipeline,
    # is genuinely blocked by this -- packages/risk/engine.py's own
    # trading_paused check (wired since "PROMPT 8") is what actually
    # enforces it, proving the mismatch above propagates end-to-end rather
    # than staying a reconciliation-layer-only assertion.
    asset = _asset(db_session, "E2ESCENARIOC")
    strategy_row = _strategy_row(db_session, "e2e_scenario_c_strategy")
    kwargs = _maybe_execute_kwargs(db_session, asset, strategy_row)
    adapter = PaperBrokerAdapter(db_session)

    outcome = maybe_execute(db_session, adapter, decision=None, **kwargs)

    assert outcome == "risk_rejected"
    assert db_session.query(Position).count() == 0
    event = (
        db_session.query(TradingEvent)
        .filter(TradingEvent.event_type == "risk_blocked", TradingEvent.entity_id == kwargs["signal_row"].id)
        .first()
    )
    assert event is not None
    assert event.payload["reason"] == "trading_paused"


# -- Scenario D (§110) -- an agent/LLM cycle never creates an order or position --
def test_scenario_d_a_full_agent_cycle_never_creates_an_order_or_a_position(db_session):
    """§110's security test: "LLM/agent attempting to create an order ->
    DENIED." AgentContext.db (packages/agents/context.py) is a real,
    writable Session -- there is no runtime sandbox stopping an agent
    module from calling db.add(Order(...)) itself. What actually enforces
    "DENIED" is that no agent implementation ever does, because no agent
    code path imports order_manager or the broker package at all --
    statically proven by tests/test_execution_red_team.py's #1-#4. This is
    the dynamic counterpart: running the ENTIRE real 18-agent cycle against
    a real seeded market and confirming it produces only a Decision, never
    an Order or a Position, in practice and not just by static proof."""
    asset = _asset(db_session, "E2ESCENARIOD")
    now = datetime.now(timezone.utc)
    price = 100.0
    for i in range(40):
        price *= 1 + (0.001 if i % 3 == 0 else -0.0005)
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe="1m", ts=now - timedelta(minutes=40 - i), open=price, high=price * 1.002, low=price * 0.998, close=price, volume=1000)
        )
    db_session.commit()

    rows = db_session.query(OHLCV).filter(OHLCV.asset_id == asset.id).order_by(OHLCV.ts.asc()).all()
    candles = [Candle(ts=r.ts, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume, data_quality="high") for r in rows]
    indicators = compute_indicators(candles)
    regime = classify_regime(candles)
    market = MarketContext(asset_id=asset.id, symbol=asset.symbol, timeframe="1m", candles=candles, indicators=indicators, regime=regime)
    quality = compute_quality_score(
        symbol=asset.symbol, latest_ts=candles[-1].ts, timeframe="1m", candle_count=len(candles),
        expected_count=200, last_data_quality="high", provider_connected=True,
    )
    ctx = AgentContext(db=db_session, market=market, asset=asset, now=now, quality_report=quality)

    decision, decision_row = run_agent_cycle(db_session, ctx)

    assert decision.decision_state in chief_decision.DECISION_STATES
    assert decision_row.id is not None
    assert db_session.query(Order).count() == 0
    assert db_session.query(Position).count() == 0


# -- Scenario E (§111) -- a live-trading attempt is blocked at the full pipeline level --
def test_scenario_e_live_trading_attempt_is_blocked_at_the_full_pipeline_level(db_session, monkeypatch):
    """§2, §97 -- even a hypothetical bug that fed maybe_execute() a
    trading_mode='live' SystemState (impossible via the DB itself -- the
    CHECK constraint forbids ever persisting that value, proven by
    test_execution_red_team.py's #6) is caught through the FULL
    maybe_execute() pipeline rather than by calling a single layer's check
    directly. In practice this reveals a FOURTH, even earlier layer beyond
    the three packages/execution/firewall.py's own docstring documents:
    packages/risk/engine.py's step 1c (present since "PROMPT 8", §2-4)
    already refuses anything but trading_mode in (None, "paper") before the
    signal ever reaches Portfolio Manager or the ExecutionGate -- so this
    is blocked as "risk_rejected", not "gate_rejected". The ExecutionGate's
    own LiveTradingFirewall check (packages/execution/gate.py) still exists
    as a redundant backstop for anything that reaches it regardless (see
    test_execution_red_team.py's #5, which exercises that layer directly)."""
    asset = _asset(db_session, "E2ESCENARIOE")
    strategy_row = _strategy_row(db_session, "e2e_scenario_e_strategy")
    kwargs = _maybe_execute_kwargs(db_session, asset, strategy_row)

    live_state = SystemState(trading_mode="live", trading_enabled=True)  # deliberately never committed -- the DB CHECK forbids persisting this
    monkeypatch.setattr(risk_execution, "_get_or_create_system_state", lambda db: live_state)

    adapter = PaperBrokerAdapter(db_session)
    outcome = maybe_execute(db_session, adapter, decision=None, **kwargs)

    assert outcome == "risk_rejected"
    assert db_session.query(Position).count() == 0
    assert db_session.query(Order).count() == 0
    event = (
        db_session.query(TradingEvent)
        .filter(TradingEvent.event_type == "risk_blocked", TradingEvent.entity_id == kwargs["signal_row"].id)
        .first()
    )
    assert event is not None
    assert event.payload["layer"] == "risk_engine"
    assert event.payload["reason"] == "live_trading_disabled"
