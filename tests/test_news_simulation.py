"""Prompt 6 §42 — full News Intelligence simulation:
normal news -> high-impact macro event -> sentiment shift -> News Risk
Guard escalates -> Opportunity confidence changes -> Risk Engine sizing
changes -> a critical event blocks entirely. Every step also checks the
one non-negotiable rule (§43/§48): the News Engine can only ever reduce or
block a trade through the Risk Engine's own check — nothing in
packages/quant/news ever approves, sizes, or submits an order itself.
"""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from packages.data.connectors.market.base import Candle
from packages.portfolio.state import PortfolioState
from packages.quant.indicators.core import compute_indicators
from packages.quant.news.sentiment import compute_sentiment_shift
from packages.quant.regime.classifier import NewsSignal, classify_regime
from packages.quant.scoring.inputs import compute_opportunity_confidence
from packages.quant.strategies.base import MarketContext
from packages.risk.config import load_risk_limits
from packages.risk.engine import SignalForRisk, evaluate_signal
from packages.shared.models import Asset, MacroEvent, NewsEvent, NewsImpact, Signal, StrategyRow, SystemState

STARTING_EQUITY = 10_000.0
LIMITS = load_risk_limits()


def _now() -> datetime:
    # Computed fresh on every call, never once at module import time -- a
    # module-level constant here would drift stale (relative to
    # config/risk_limits.yaml's max_staleness_seconds=120) on a slow full-
    # suite run, since this test isn't necessarily the first to execute.
    return datetime.now(timezone.utc)


def _state(now: datetime, **overrides) -> PortfolioState:
    base = dict(
        ts=now, cash=STARTING_EQUITY, equity=STARTING_EQUITY, exposure_pct=0.0,
        daily_pnl=0.0, daily_loss_pct=0.0, weekly_pnl=0.0, weekly_loss_pct=0.0,
        monthly_pnl=0.0, monthly_loss_pct=0.0, drawdown_pct=0.0, unrealized_pnl=0.0, open_positions=[],
    )
    base.update(overrides)
    return PortfolioState(**base)


def _signal(db_session, asset, now: datetime) -> SignalForRisk:
    strategy = db_session.query(StrategyRow).filter(StrategyRow.code == "news_simulation_strategy").first()
    if strategy is None:
        strategy = StrategyRow(code="news_simulation_strategy", name="News Simulation", family="trend", version="1.0")
        db_session.add(strategy)
        db_session.commit()
    signal_row = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=now, direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="scored",
    )
    db_session.add(signal_row)
    db_session.commit()
    return SignalForRisk(
        signal_id=signal_row.id, asset_id=asset.id, strategy_id=strategy.id, direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, risk_reward=3.0, confidence=1.0,
        volatility_factor=1.0, data_quality="high", data_ts=now, tier="high_quality", asset_class=asset.asset_class,
    )


def test_full_news_escalation_simulation(db_session):
    now = _now()
    trading_on = SystemState(id=True, trading_enabled=True)
    asset = Asset(symbol="NEWSSIMASSET", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    # --- Step 1: normal news, no macro events -> NORMAL event risk, full size.
    db_session.add(NewsEvent(
        source="Reuters", published_at=now - timedelta(minutes=30), headline="Routine market commentary",
        category="other", importance="low", sentiment="neutral",
    ))
    db_session.commit()

    baseline = evaluate_signal(db_session, _signal(db_session, asset, now), _state(now), trading_on, LIMITS)
    assert baseline.approved
    assert baseline.safety_belt_level  # sanity: a real belt was computed
    baseline_quantity = baseline.approved_quantity
    assert baseline_quantity == pytest.approx(15.0)  # same hand-derived math as test_risk_simulation.py

    # --- Step 2: a HIGH-importance macro event becomes imminent -> News Risk
    # Guard escalates to HIGH -> size reduced by exactly its configured
    # multiplier, never blocked outright.
    db_session.add(MacroEvent(
        event="Simulated CPI Release", country="US", currency="USD",
        scheduled_at=now + timedelta(minutes=10), importance="high",
        forecast=3.0, previous=2.9, status="scheduled",
    ))
    db_session.commit()

    reduced = evaluate_signal(db_session, _signal(db_session, asset, now), _state(now), trading_on, LIMITS)
    assert reduced.approved  # HIGH reduces, does not block
    expected_multiplier = LIMITS.news_risk_multipliers.high
    assert reduced.approved_quantity == pytest.approx(baseline_quantity * expected_multiplier)
    assert reduced.approved_quantity < baseline_quantity

    # --- Step 3: sentiment shift building for this asset (feeds the
    # dashboard's SENTIMENT_SHIFT signal, §22) -- descriptive only, must not
    # itself alter Risk Engine sizing (only the News Risk Guard/opportunity
    # confidence paths may).
    for _ in range(4):
        event = NewsEvent(
            source="Reuters", published_at=now - timedelta(hours=20), headline="Baseline bullish coverage",
            category="other", sentiment="bullish",
        )
        db_session.add(event)
        db_session.commit()
        db_session.add(NewsImpact(news_event_id=event.id, asset_id=asset.id, impact="medium", direction="bullish", confidence=0.6, horizon_hours=12, rationale="t"))
    for _ in range(3):
        event = NewsEvent(
            source="Bloomberg", published_at=now - timedelta(minutes=30), headline="Recent bearish turn",
            category="other", sentiment="bearish",
        )
        db_session.add(event)
        db_session.commit()
        db_session.add(NewsImpact(news_event_id=event.id, asset_id=asset.id, impact="medium", direction="bearish", confidence=0.6, horizon_hours=12, rationale="t"))
    db_session.commit()

    shift = compute_sentiment_shift(db_session, asset.id)
    assert shift.detected is True

    # Sizing is still governed only by the belt/health/news-risk multipliers
    # actually wired into engine.py -- an ordinary sentiment shift, on its
    # own, changes no size (§22: "Não transformar automaticamente em trade").
    still_reduced_only_by_news_risk = evaluate_signal(db_session, _signal(db_session, asset, now), _state(now), trading_on, LIMITS)
    assert still_reduced_only_by_news_risk.approved_quantity == pytest.approx(reduced.approved_quantity)

    # --- Step 4: Opportunity confidence reacts to a technical/news conflict
    # (§27-28) -- a long technical signal against a confidently bearish news
    # read lowers confidence, never flips the signal or blocks it directly;
    # only the Risk Engine (already exercised above) has that power.
    candles = []
    price = 100.0
    for i in range(40):
        price += 0.5
        candles.append(Candle(ts=now - timedelta(minutes=40 - i), open=price - 0.1, high=price + 0.2, low=price - 0.2, close=price, volume=100, data_quality="high"))
    ctx = MarketContext(asset_id=asset.id, symbol=asset.symbol, timeframe="1m", candles=candles, indicators=compute_indicators(candles), regime=classify_regime(candles))

    no_news_confidence, _ = compute_opportunity_confidence(ctx, [], "long", 0.5, 0.5)
    bearish_news = [NewsSignal(direction="bearish", impact="high", confidence=0.9)]
    conflicted_confidence, notes = compute_opportunity_confidence(ctx, [], "long", 0.5, 0.5, news_signals=bearish_news)
    assert conflicted_confidence < no_news_confidence
    assert notes["news_conflict"] is True

    # --- Step 5: the macro event's importance escalates to CRITICAL and
    # remains imminent -> News Risk Guard escalates to CRITICAL -> blocked
    # outright, the one point where News Intelligence can veto a trade --
    # and even then only by routing through the Risk Engine's own check,
    # exactly like every other block reason in packages/risk/engine.py.
    macro_event = db_session.query(MacroEvent).filter(MacroEvent.event == "Simulated CPI Release").first()
    macro_event.importance = "critical"
    db_session.commit()

    blocked = evaluate_signal(db_session, _signal(db_session, asset, now), _state(now), trading_on, LIMITS)
    assert not blocked.approved
    assert blocked.reason == "news_risk_critical"
    assert blocked.approved_quantity is None

    # --- Structural proof of sovereignty (§43/§48): nothing in the News
    # Intelligence package imports the Execution Engine or constructs a
    # RiskVerdict/RiskDecision itself -- its only export the Risk Engine
    # consumes is a size multiplier + blocked flag (packages/risk/news_guard.py),
    # never an approval.
    news_package_dir = Path(__file__).resolve().parents[1] / "packages" / "quant" / "news"
    for py_file in news_package_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "packages.execution" not in node.module, f"{py_file.name} must never import execution"
                assert "RiskVerdict" not in [a.name for a in node.names]
                assert "RiskDecision" not in [a.name for a in node.names]
