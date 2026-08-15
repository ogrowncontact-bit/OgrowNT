"""Opportunity Scoring Engine — docs/blueprint/07-scoring-engine.md.

Deterministic. Every input is 0-100 (already normalized by the caller);
every penalty is a 0.0-1.0 fraction of its configured cap. Nothing here
calls a strategy, the DB, or an LLM — it is a pure function of its inputs,
which is what makes every score reproducible and auditable (the "Why?"
panel in docs/blueprint/09-dashboard-spec.md is this function's output).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.quant.scoring.config import ScoringConfig, Thresholds, load_scoring_config


@dataclass(frozen=True)
class ScoringInputs:
    technical: float
    pattern: float
    regime_fit: float
    historical_edge: float
    liquidity: float
    news: float
    risk_reward: float
    strategy_performance: float
    volatility_penalty: float = 0.0
    correlation_penalty: float = 0.0
    execution_cost_penalty: float = 0.0
    drawdown_penalty: float = 0.0
    notes: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OpportunityScore:
    technical: float
    pattern: float
    regime_fit: float
    historical_edge: float
    liquidity: float
    news: float
    risk_reward: float
    strategy_performance: float
    volatility_penalty_points: float
    correlation_penalty_points: float
    execution_cost_penalty_points: float
    drawdown_penalty_points: float
    final_score: float
    tier: str


def tier_for(score: float, thresholds: Thresholds) -> str:
    if score < thresholds.ignore:
        return "ignore"
    if score < thresholds.watch:
        return "watch"
    if score < thresholds.possible:
        return "possible"
    if score < thresholds.high_quality:
        return "high_quality"
    return "exceptional"


def compute_score(inputs: ScoringInputs, cfg: ScoringConfig | None = None) -> OpportunityScore:
    cfg = cfg or load_scoring_config()
    w = cfg.weights

    base = (
        inputs.technical * w.technical
        + inputs.pattern * w.pattern
        + inputs.regime_fit * w.regime
        + inputs.historical_edge * w.historical_edge
        + inputs.liquidity * w.liquidity
        + inputs.news * w.news
        + inputs.risk_reward * w.risk_reward
        + inputs.strategy_performance * w.strategy_performance
    )

    p = cfg.penalties
    volatility_pts = inputs.volatility_penalty * p.volatility_max
    correlation_pts = inputs.correlation_penalty * p.correlation_max
    execution_cost_pts = inputs.execution_cost_penalty * p.execution_cost_max
    drawdown_pts = inputs.drawdown_penalty * p.drawdown_max

    final = max(0.0, min(100.0, base - (volatility_pts + correlation_pts + execution_cost_pts + drawdown_pts)))

    return OpportunityScore(
        technical=inputs.technical,
        pattern=inputs.pattern,
        regime_fit=inputs.regime_fit,
        historical_edge=inputs.historical_edge,
        liquidity=inputs.liquidity,
        news=inputs.news,
        risk_reward=inputs.risk_reward,
        strategy_performance=inputs.strategy_performance,
        volatility_penalty_points=round(volatility_pts, 2),
        correlation_penalty_points=round(correlation_pts, 2),
        execution_cost_penalty_points=round(execution_cost_pts, 2),
        drawdown_penalty_points=round(drawdown_pts, 2),
        final_score=round(final, 2),
        tier=tier_for(final, cfg.thresholds),
    )
