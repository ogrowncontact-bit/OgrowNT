"""Builds ScoringInputs from a strategy's read of the market — the bridge
between the Strategy/Pattern/News/Learning Engines and the Opportunity
Scoring Engine (docs/blueprint/07-scoring-engine.md).

One input the full formula calls for still doesn't exist as a real signal:
Portfolio/Risk Engine's own penalties are computed by packages/risk itself,
not here. Per docs/blueprint/00-overview.md's "no hallucinated data" rule,
that stays an explicit neutral 50/0, never a fabricated number.

`pattern` and `news` were neutral 50 through Phase 2/3 — as of Phase 4 they
use real Pattern Engine detections and real (or, without an LLM configured,
absent) news_impact reads. `historical_edge` and `strategy_performance`
were neutral 50 through Phase 4 — as of Phase 5 they use real Pattern/
Strategy Memory (docs/blueprint/06-memory-system.md): `historical_edge` is
"expectancy histórica em condições semelhantes" per 07-scoring-engine.md's
component table (Pattern Memory + Strategy Memory), `strategy_performance`
is the strategy's own recent Health Score
(packages/quant/learning/strategy_stats.py). Both still degrade honestly to
neutral 50 when there isn't yet enough sample to trust — the caller
(apps/worker/strategy_runner.py) is the one deciding "do we have this data
at all" via its own minimum-sample gates; this module only turns an
already-vetted expectancy/score into a 0-100 component.
"""
from __future__ import annotations

from packages.quant.indicators.core import data_quality_confidence
from packages.quant.patterns.detector import PatternDetection
from packages.quant.regime.classifier import REGIME_HIGH_VOLATILITY, NewsSignal
from packages.quant.scoring.engine import ScoringInputs
from packages.quant.strategies.base import AnalysisResult, MarketContext, Strategy, StrategySignal

# Default confidence.pattern_confidence when no pattern aligned with the
# signal direction -- "no supporting pattern" is a scoring fact (already
# reflected in the neutral 50 pattern score), not a confidence problem, so
# this stays a fixed neutral rather than 0.0.
_NO_ALIGNED_PATTERN_CONFIDENCE = 0.6
# confidence.history_confidence when neither pattern nor strategy expectancy
# had a real sample -- Prompt 3 §18's INSUFFICIENT_HISTORY, expressed as a
# reduced confidence rather than a fabricated number.
_INSUFFICIENT_HISTORY_CONFIDENCE = 0.4

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


def _expectancy_to_score(expectancy: float | None) -> float:
    """Same linear map packages/quant/learning/strategy_stats.py uses for
    its health score's expectancy component — an R-multiple expectancy of 0
    is neutral (50), +/-2R saturates the score. None (no sample yet trusted
    by the caller) is the honest neutral default, not a guess."""
    if expectancy is None:
        return 50.0
    return round(max(0.0, min(100.0, 50.0 + expectancy * 25.0)), 2)


def build_scoring_inputs(
    ctx: MarketContext,
    strategy: Strategy,
    analysis: AnalysisResult,
    signal: StrategySignal,
    patterns: list[PatternDetection] | None = None,
    news_signals: list[NewsSignal] | None = None,
    pattern_expectancy: float | None = None,
    strategy_expectancy: float | None = None,
    strategy_health_score: float | None = None,
) -> ScoringInputs:
    technical = round(analysis.strength * 100, 2)
    regime_fit = round(strategy.regime_fit(ctx.regime.regime) * 100, 2)
    risk_reward_score = round(min(100.0, (signal.risk_reward / TARGET_RISK_REWARD_FOR_FULL_SCORE) * 100), 2)
    liquidity = round(_liquidity_proxy(ctx), 2)
    pattern_score, pattern_note = _pattern_score(signal.direction, patterns or [])
    news_score, news_note = _news_score(signal.direction, news_signals or [])

    pattern_edge_score = _expectancy_to_score(pattern_expectancy)
    strategy_edge_score = _expectancy_to_score(strategy_expectancy)
    historical_edge = round((pattern_edge_score + strategy_edge_score) / 2, 2)
    strategy_performance_score = round(strategy_health_score, 2) if strategy_health_score is not None else 50.0

    return ScoringInputs(
        technical=technical,
        pattern=pattern_score,
        regime_fit=regime_fit,
        historical_edge=historical_edge,
        liquidity=liquidity,
        news=news_score,
        risk_reward=risk_reward_score,
        strategy_performance=strategy_performance_score,
        volatility_penalty=_volatility_penalty_fraction(ctx),
        correlation_penalty=0.0,
        execution_cost_penalty=0.0,
        drawdown_penalty=0.0,
        notes={
            "pattern": pattern_note,
            "news": news_note,
            "historical_edge": {
                "pattern_expectancy": pattern_expectancy,
                "strategy_expectancy": strategy_expectancy,
                # Prompt 3 §18: explicit, not just a silently neutral score.
                "insufficient_history": pattern_expectancy is None and strategy_expectancy is None,
            },
            "strategy_performance": {"health_score": strategy_health_score},
        },
    )


def compute_opportunity_confidence(
    ctx: MarketContext,
    patterns: list[PatternDetection],
    signal_direction: str,
    pattern_expectancy: float | None,
    strategy_expectancy: float | None,
) -> tuple[float, dict]:
    """0-100: how much the inputs behind this Opportunity's score can be
    trusted -- shown separately from final_score, never as a proxy for it
    (Prompt 3 §17/§20 "Nunca tratar score como probabilidade real").

    Deliberately a small, auditable average of four already-real signals
    (data quality, regime confidence, the best aligned pattern's own
    confidence, whether historical_edge had a real sample) rather than a
    fabricated single number -- every component here is something another
    part of the system already computed, not a new opinion.
    """
    quality_confidence = data_quality_confidence(ctx.candles)
    regime_confidence = ctx.regime.confidence

    aligned = [p for p in patterns if _alignment(signal_direction, p.direction) == 1]
    pattern_confidence = max((p.confidence for p in aligned), default=_NO_ALIGNED_PATTERN_CONFIDENCE)

    insufficient_history = pattern_expectancy is None and strategy_expectancy is None
    history_confidence = _INSUFFICIENT_HISTORY_CONFIDENCE if insufficient_history else 1.0

    components = {
        "data_quality": round(quality_confidence, 3),
        "regime": round(regime_confidence, 3),
        "pattern": round(pattern_confidence, 3),
        "history": round(history_confidence, 3),
    }
    overall = sum(components.values()) / len(components)
    return round(max(0.0, min(100.0, overall * 100)), 2), {
        "components": components,
        "insufficient_history": insufficient_history,
    }
