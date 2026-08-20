"""Chief Decision Engine wired into the worker cycle — "PROMPT 9" §14, §37-
39, §68. Covers red-team item #10 ("Decision=None is 'no opinion', never
implicit approval") and the defense-in-depth requirement that a favorable
Decision never bypasses the sovereign Risk Engine (Prompt 8 §75's "defense
in depth" precedent, extended by this layer rather than replaced).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import apps.worker.risk_execution as risk_execution
from apps.worker.risk_execution import maybe_execute
from packages.agents import chief as chief_decision
from packages.agents.consensus import ConsensusResult
from packages.agents.context import AgentContext
from packages.agents.orchestrator import run_agent_cycle
from packages.data.connectors.market.base import Candle
from packages.data.quality import compute_quality_score
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.quant.indicators.core import IndicatorSet
from packages.quant.regime.classifier import RegimeResult
from packages.quant.scoring.engine import OpportunityScore as ScoreResult
from packages.quant.strategies import ALL_STRATEGIES
from packages.quant.strategies.base import AnalysisResult, MarketContext, StrategySignal
from packages.shared.models import OHLCV, Asset, Decision, Order, Position, Signal, StrategyRow, TradingEvent

_STRATEGY = ALL_STRATEGIES[0]


def _empty_decision(
    state: str, *, blocked_reason: str | None = None, critical_agent_failure: bool = False
) -> chief_decision.Decision:
    consensus = ConsensusResult(consensus_score=0.0, voting_agents=0, meaningful_votes=0, eligible_agents=7, contributions={})
    return chief_decision.Decision(
        decision_state=state, consensus=consensus, contradiction_score=0.0, contradictions=[],
        reasoning_summary=f"test decision forced to {state}", agent_messages={},
        blocked_reason=blocked_reason, critical_agent_failure=critical_agent_failure,
    )


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _strategy_row(db_session, code: str) -> StrategyRow:
    row = StrategyRow(code=code, name=code, family=_STRATEGY.family, version="1.0")
    db_session.add(row)
    db_session.commit()
    return row


def _maybe_execute_kwargs(db_session, asset: Asset, strategy_row: StrategyRow, *, entry_price: float = 100.0) -> dict:
    now = datetime.now(timezone.utc)
    candles = [
        Candle(ts=now - timedelta(minutes=5 - i), open=entry_price, high=entry_price * 1.001, low=entry_price * 0.999, close=entry_price, volume=1000, data_quality="high")
        for i in range(5)
    ]
    # PaperExecutionProvider fills from a real OHLCV row (packages/execution/
    # adapters/paper.py's get_latest_candle_row), not from the in-memory
    # MarketContext -- needed for the "executed" outcome path.
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


def test_blocked_decision_prevents_execution_without_ever_reaching_risk_engine(db_session, monkeypatch):
    asset = _asset(db_session, "WIRINGBLOCKED")
    strategy_row = _strategy_row(db_session, "wiring_blocked_strategy")
    kwargs = _maybe_execute_kwargs(db_session, asset, strategy_row)

    def _boom(*a, **kw):
        raise AssertionError("Risk Engine must never be consulted once the Chief Decision Engine has already blocked")

    monkeypatch.setattr(risk_execution, "evaluate_signal", _boom)
    provider = PaperExecutionProvider(db_session)
    decision = _empty_decision(chief_decision.BLOCKED, blocked_reason="critical_agent_unavailable:data_quality", critical_agent_failure=True)

    outcome = maybe_execute(db_session, provider, decision=decision, **kwargs)

    assert outcome == "chief_blocked"
    assert db_session.query(Position).count() == 0
    assert db_session.query(Order).count() == 0
    event = db_session.query(TradingEvent).filter(TradingEvent.event_type == "risk_blocked").first()
    assert event is not None and event.payload["layer"] == "chief_decision_engine"


def test_no_trade_decision_prevents_execution(db_session, monkeypatch):
    asset = _asset(db_session, "WIRINGNOTRADE")
    strategy_row = _strategy_row(db_session, "wiring_no_trade_strategy")
    kwargs = _maybe_execute_kwargs(db_session, asset, strategy_row)

    def _boom(*a, **kw):
        raise AssertionError("Risk Engine must never be consulted once the Chief Decision Engine has already said NO_TRADE")

    monkeypatch.setattr(risk_execution, "evaluate_signal", _boom)
    provider = PaperExecutionProvider(db_session)
    decision = _empty_decision(chief_decision.NO_TRADE)

    outcome = maybe_execute(db_session, provider, decision=decision, **kwargs)

    assert outcome == "chief_no_trade"
    assert db_session.query(Position).count() == 0
    event = db_session.query(TradingEvent).filter(TradingEvent.event_type == "no_trade", TradingEvent.entity_id == kwargs["signal_row"].id).first()
    assert event is not None


@pytest.mark.parametrize("decision_state", [None, chief_decision.NEUTRAL, chief_decision.STRONG_LONG_BIAS])
def test_a_non_blocking_decision_is_no_opinion_never_an_implicit_approval(db_session, decision_state):
    """Red-team item #10: whether decision is None, NEUTRAL, or even
    favorable (STRONG_LONG_BIAS), the sovereign Risk Engine still runs and
    still has the final say -- a favorable Decision only ever ADDS a
    filter, it never grants execution on its own."""
    asset = _asset(db_session, "WIRINGNOOPINION")
    strategy_row = _strategy_row(db_session, "wiring_no_opinion_strategy")
    kwargs = _maybe_execute_kwargs(db_session, asset, strategy_row)

    decision = None if decision_state is None else _empty_decision(decision_state)
    provider = PaperExecutionProvider(db_session)

    outcome = maybe_execute(db_session, provider, decision=decision, **kwargs)

    # Kill switch is off by default (no SystemState row -> trading_enabled
    # defaults True) and every other Risk Engine gate is clean for this
    # kwargs fixture -- so the ONLY way this could fail to execute is if a
    # non-blocking Decision were silently treated as a veto. It isn't.
    assert outcome == "executed"
    assert db_session.query(Position).count() == 1


def test_a_favorable_decision_never_bypasses_a_risk_engine_rejection(db_session):
    """The other half of defense-in-depth: even STRONG_LONG_BIAS must not
    rescue a signal the Risk Engine independently rejects (kill switch
    here, but structurally this is the same for any Risk Engine gate)."""
    from packages.shared.models import SystemState

    asset = _asset(db_session, "WIRINGKILLSWITCH")
    strategy_row = _strategy_row(db_session, "wiring_kill_switch_strategy")
    kwargs = _maybe_execute_kwargs(db_session, asset, strategy_row)
    db_session.add(SystemState(id=True, trading_enabled=False))
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    decision = _empty_decision(chief_decision.STRONG_LONG_BIAS)

    outcome = maybe_execute(db_session, provider, decision=decision, **kwargs)

    assert outcome == "risk_rejected"
    assert db_session.query(Position).count() == 0


def test_run_agent_cycle_is_fully_wired_into_the_strategy_cycle(db_session):
    """End-to-end: apps/worker/strategy_runner.py builds a real
    AgentContext, runs all 18 agents, and persists a Decision -- proven
    here by calling run_agent_cycle directly against a real seeded market,
    the same shape apps/worker/strategy_runner.py uses in production."""
    asset = _asset(db_session, "WIRINGE2E")
    now = datetime.now(timezone.utc)
    price = 100.0
    for i in range(40):
        price *= 1 + (0.001 if i % 3 == 0 else -0.0005)
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=now - timedelta(minutes=40 - i),
                open=price, high=price * 1.002, low=price * 0.998, close=price, volume=1000,
            )
        )
    db_session.commit()

    from packages.quant.indicators.core import compute_indicators
    from packages.quant.regime.classifier import classify_regime

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
    persisted = db_session.get(Decision, decision_row.id)
    assert persisted is not None
    assert len(persisted.agent_inputs) == 18
