"""Builds ScoringInputs from a strategy's read of the market — the bridge
between the Strategy/Pattern/News Engines and the Opportunity Scoring
Engine (docs/blueprint/07-scoring-engine.md).

Two inputs the full formula calls for still don't exist as real signals:
Learning/Strategy Memory (historical edge, strategy performance) is Phase
5, Portfolio/Risk Engine's own penalties are computed by packages/risk
itself, not here. Per docs/blueprint/00-overview.md's "no hallucinated
data" rule, those stay an explicit neutral 50, never a fabricated number.

`pattern` and `news` were the same neutral 50 through Phase 2/3 — as of
Phase 4 they use real Pattern Engine detections and real (or, without an
LLM configured, absent) news_impact reads, scored by whether they agree or
conflict with the signal's direction.
"""
from __future__ import annotations

from packages.quant.patterns.detector import PatternDetection
from packages.quant.regime.classifier import REGIME_HIGH_VOLATILITY, NewsSignal
from packages.quant.scoring.engine import ScoringInputs
from packages.quant.strategies.base import AnalysisResult, MarketContext, Strategy, StrategySignal

PHASE5_NEUTRAL_DEFAULTS = ("historical_edge", "strategy_performance")
TARGET_RISK_REWARD_FOR_FULL_SCORE = 3.0
_IMPACT_WEIGHT = {"low": 0.3, "medium": 0.6, "high": 1.0}


def _liquidity_proxy(ctx: MarketContext) -> float:
    """Volume-relative-to-average as a stand-in for real orderbook depth
    (docs/blueprint/08-risk-engine.md's spread/depth checks need a real
    market data provider).
    """
    avg_vol = ctx.indicators.avg_volume_20
    current_vol = ctx.candles[-1].volume
    if not avg_vol:
        return 50.0
    return max(0.0, min(100.0, (current_vol / avg_vol) * 50))


def _volatility_penalty_fraction(ctx: MarketContext) -> float:
    if ctx.regime.regime == REGIME_HIGH_VOLATILITY:
        return min(1.0, ctx.regime.confidence)
    return 0.0


def _alignment(signal_direction: str, other_direction: str) -> int:
    """+1 agrees with the signal, -1 conflicts, 0 neutral/no read."""
    mapped = "bullish" if signal_direction == "long" else "bearish"
    if other_direction == mapped:
        return 1
    if other_direction in ("bullish", "bearish"):
        return -1
    return 0


def _pattern_score(signal_direction: str, patterns: list[PatternDetection]) -> tuple[float, dict]:
    if not patterns:
        return 50.0, {"pattern_detected": False}
    best = max(patterns, key=lambda p: p.strength)
    alignment = _alignment(signal_direction, best.direction)
    if alignment == 0:
        return 50.0, {"pattern_detected": True, "pattern_type": best.pattern_type, "aligned": None}
    score = 50.0 + alignment * best.strength * 50.0
    return round(max(0.0, min(100.0, score)), 2), {
        "pattern_detected": True, "pattern_type": best.pattern_type,
        "aligned": alignment == 1, "strength": best.strength,
    }


def _news_score(signal_direction: str, news_signals: list[NewsSignal]) -> tuple[float, dict]:
    if not news_signals:
        return 50.0, {"news_count": 0}
    best = max(news_signals, key=lambda n: n.confidence * _IMPACT_WEIGHT.get(n.impact, 0.5))
    alignment = _alignment(signal_direction, best.direction)
    if alignment == 0:
        return 50.0, {"news_count": len(news_signals), "aligned": None}
    weight = _IMPACT_WEIGHT.get(best.impact, 0.5) * best.confidence
    score = 50.0 + alignment * weight * 50.0
    return round(max(0.0, min(100.0, score)), 2), {
        "news_count": len(news_signals), "aligned": alignment == 1,
        "confidence": best.confidence, "impact": best.impact,
    }


def build_scoring_inputs(
    ctx: MarketContext,
    strategy: Strategy,
    analysis: AnalysisResult,
    signal: StrategySignal,
    patterns: list[PatternDetection] | None = None,
    news_signals: list[NewsSignal] | None = None,
) -> ScoringInputs:
    technical = round(analysis.strength * 100, 2)
    regime_fit = round(strategy.regime_fit(ctx.regime.regime) * 100, 2)
    risk_reward_score = round(min(100.0, (signal.risk_reward / TARGET_RISK_REWARD_FOR_FULL_SCORE) * 100), 2)
    liquidity = round(_liquidity_proxy(ctx), 2)
    pattern_score, pattern_note = _pattern_score(signal.direction, patterns or [])
    news_score, news_note = _news_score(signal.direction, news_signals or [])

    return ScoringInputs(
        technical=technical,
        pattern=pattern_score,
        regime_fit=regime_fit,
        historical_edge=50.0,
        liquidity=liquidity,
        news=news_score,
        risk_reward=risk_reward_score,
        strategy_performance=50.0,
        volatility_penalty=_volatility_penalty_fraction(ctx),
        correlation_penalty=0.0,
        execution_cost_penalty=0.0,
        drawdown_penalty=0.0,
        notes={"phase5_neutral_defaults": PHASE5_NEUTRAL_DEFAULTS, "pattern": pattern_note, "news": news_note},
    )
