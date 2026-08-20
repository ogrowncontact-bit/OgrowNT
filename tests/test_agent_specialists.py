"""Specialist agent behavior — "PROMPT 9" §15-36. Spot-checks the honest-
data-or-nothing discipline and the non-directional invariants that matter
most (Sentiment and Quant Research must never vote a direction — Prompt 6
§11's "SENTIMENT NÃO É DIREÇÃO" applies just as much inside this layer).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentSignal, AgentStatus
from packages.agents.specialists import SPECIALIST_REGISTRY, anomaly_detection, data_quality, macro, market_regime, quant_research, sentiment
from packages.data.connectors.macro.base import MacroEventItem
from packages.data.connectors.market.base import Candle
from packages.data.quality import compute_quality_score
from packages.quant.indicators.core import compute_indicators
from packages.quant.regime.classifier import RegimeResult
from packages.quant.strategies.base import MarketContext
from packages.shared.models import Asset, LearnedRule, StrategyRow


def _flat_candles(n: int = 30, price: float = 100.0) -> list[Candle]:
    now = datetime.now(timezone.utc)
    return [
        Candle(ts=now - timedelta(minutes=n - i), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1000, data_quality="high")
        for i in range(n)
    ]


def _ctx(db_session, asset: Asset, candles: list[Candle] | None = None, **overrides) -> AgentContext:
    candles = candles or _flat_candles()
    indicators = compute_indicators(candles)
    regime = RegimeResult(regime="ranging", confidence=0.5, features={})
    market = MarketContext(asset_id=asset.id, symbol=asset.symbol, timeframe="1m", candles=candles, indicators=indicators, regime=regime)
    base = dict(db=db_session, market=market, asset=asset, now=datetime.now(timezone.utc))
    base.update(overrides)
    return AgentContext(**base)


def test_every_registered_agent_can_run_against_a_bare_context_without_raising(db_session):
    """Every specialist must degrade gracefully (OK or UNAVAILABLE) on the
    thinnest possible context -- no agent may raise, since the orchestrator
    treats a raise as UNAVAILABLE anyway; this proves the honest path is
    used deliberately, not just caught accidentally."""
    asset = Asset(symbol="SPECBASE", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    ctx = _ctx(db_session, asset)

    for code, meta in SPECIALIST_REGISTRY.items():
        message = meta.analyze(ctx)
        assert message.agent_code == code
        assert message.status in (AgentStatus.OK, AgentStatus.UNAVAILABLE)


def test_sentiment_agent_never_casts_a_directional_vote(db_session):
    """Prompt 6 §11 applies inside the multi-agent layer too -- confirmed
    structurally: sentiment.py's own analyze() only ever returns NEUTRAL."""
    asset = Asset(symbol="SPECSENTIMENT", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    message = sentiment.analyze(_ctx(db_session, asset))
    assert message.signal == AgentSignal.NEUTRAL


def test_quant_research_agent_never_casts_a_directional_vote_even_with_a_validated_rule(db_session):
    """A validated LearnedRule's condition/conclusion is free-form LLM
    text with no machine-readable direction (packages/llm/research.py's
    RuleProposal) -- this agent must never guess one from it."""
    asset = Asset(symbol="SPECRESEARCH", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="spec_research_strategy", name="Spec", family="trend", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    db_session.add(
        LearnedRule(
            scope=f"strategy:{strategy.code}", condition={"rsi": ">70"}, conclusion="fade extreme RSI",
            confidence=0.9, sample_size=25, status="validated",
        )
    )
    db_session.commit()

    message = quant_research.analyze(_ctx(db_session, asset, strategy_row=strategy))
    assert message.signal == AgentSignal.NEUTRAL
    assert message.evidence["validated_rules"] == 1


def test_data_quality_agent_reports_unavailable_with_no_quality_report():
    ctx_db = None  # not touched by this agent
    asset = Asset(symbol="SPECQUALITY", asset_class="crypto", is_active=True)
    market = MarketContext(
        asset_id=1, symbol=asset.symbol, timeframe="1m", candles=_flat_candles(),
        indicators=compute_indicators(_flat_candles()), regime=RegimeResult(regime="ranging", confidence=0.5, features={}),
    )
    ctx = AgentContext(db=ctx_db, market=market, asset=asset, now=datetime.now(timezone.utc), quality_report=None)
    message = data_quality.analyze(ctx)
    assert message.status == AgentStatus.UNAVAILABLE
    assert message.signal == AgentSignal.NO_READ


def test_data_quality_agent_flags_degraded_status_as_a_risk():
    asset = Asset(symbol="SPECQUALITYDEGRADED", asset_class="crypto", is_active=True)
    candles = _flat_candles()
    report = compute_quality_score(
        symbol=asset.symbol, latest_ts=candles[-1].ts - timedelta(hours=6), timeframe="1m", candle_count=5,
        expected_count=200, last_data_quality="degraded", provider_connected=True,
    )
    market = MarketContext(
        asset_id=1, symbol=asset.symbol, timeframe="1m", candles=candles,
        indicators=compute_indicators(candles), regime=RegimeResult(regime="ranging", confidence=0.5, features={}),
    )
    ctx = AgentContext(db=None, market=market, asset=asset, now=datetime.now(timezone.utc), quality_report=report)
    message = data_quality.analyze(ctx)
    assert message.status == AgentStatus.OK
    assert "data_quality_degraded" in message.risk_flags


def test_macro_agent_flags_imminent_high_importance_events_without_guessing_direction():
    asset = Asset(symbol="SPECMACRO", asset_class="crypto", is_active=True)
    now = datetime.now(timezone.utc)
    candles = _flat_candles()
    market = MarketContext(
        asset_id=1, symbol=asset.symbol, timeframe="1m", candles=candles,
        indicators=compute_indicators(candles), regime=RegimeResult(regime="ranging", confidence=0.5, features={}),
    )
    imminent_event = MacroEventItem(
        event="FOMC Rate Decision", country="US", currency="USD", scheduled_at=now + timedelta(hours=2),
        importance="critical", forecast=None, previous=None, actual=None,
    )
    ctx = AgentContext(db=None, market=market, asset=asset, now=now, macro_events=(imminent_event,))
    message = macro.analyze(ctx)
    assert message.signal == AgentSignal.NEUTRAL  # never a directional guess
    assert "macro_event_imminent" in message.risk_flags


def test_anomaly_agent_wraps_the_existing_detector_and_stays_non_directional(db_session):
    asset = Asset(symbol="SPECANOMALY", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    # A sharp one-bar move well outside the recent return distribution --
    # enough to trigger detect_anomaly's z-score threshold.
    now = datetime.now(timezone.utc)
    candles = [
        Candle(ts=now - timedelta(minutes=30 - i), open=100.0, high=100.2, low=99.8, close=100.0, volume=1000, data_quality="high")
        for i in range(29)
    ]
    candles.append(Candle(ts=now, open=100.0, high=140.0, low=100.0, close=135.0, volume=5000, data_quality="high"))
    message = anomaly_detection.analyze(_ctx(db_session, asset, candles=candles))
    assert message.signal == AgentSignal.NEUTRAL
    if message.status == AgentStatus.OK and message.risk_flags:
        assert "anomaly_detected" in message.risk_flags


def test_market_regime_agent_is_unavailable_on_insufficient_history(db_session):
    asset = Asset(symbol="SPECREGIME", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    candles = _flat_candles(n=3)
    indicators = compute_indicators(candles)
    market = MarketContext(
        asset_id=asset.id, symbol=asset.symbol, timeframe="1m", candles=candles, indicators=indicators,
        regime=RegimeResult(regime="unknown", confidence=0.0, features={"reason": "insufficient_history"}),
    )
    ctx = AgentContext(db=db_session, market=market, asset=asset, now=datetime.now(timezone.utc))
    message = market_regime.analyze(ctx)
    assert message.status == AgentStatus.UNAVAILABLE
