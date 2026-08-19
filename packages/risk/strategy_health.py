"""Strategy Health Guard — docs/blueprint/08-risk-engine.md#strategy-health.

Consults the same health_score the Learning Agent already computes
(packages/quant/learning/strategy_stats.py) and the same quarantine
threshold it already enforces (packages/quant/learning/quarantine.py) to
turn a strategy's rolling performance into a Risk Engine action: healthy =>
no change, warning => logged only, degraded => reduce size, quarantined =>
block. apps/worker/strategy_runner.py already filters lifecycle_stage=
'quarantine' strategies out before a signal is generated, so the
"quarantined" branch here is a defensive second check, not the primary
enforcement point — a module with veto power over every trade should never
rely on a single upstream filter alone.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.quant.learning.quarantine import HEALTH_SCORE_QUARANTINE_THRESHOLD

HEALTHY = "healthy"
WARNING = "warning"
DEGRADED = "degraded"
QUARANTINED = "quarantined"

# Between the quarantine threshold and this, a strategy is trending toward
# quarantine but not there yet — risk is reduced, not blocked, mirroring the
# Safety Belt's DEFENSIVE (reduce) vs KILL_SWITCH (block) split.
DEGRADED_THRESHOLD = 45.0
WARNING_THRESHOLD = 60.0

DEGRADED_SIZE_MULTIPLIER = 0.5


@dataclass(frozen=True)
class StrategyHealthVerdict:
    status: str
    size_multiplier: float
    blocked: bool


def classify_strategy_health(health_score: float | None) -> StrategyHealthVerdict:
    """`health_score` is None when the strategy has too few closed trades to
    judge yet (packages/quant/learning/strategy_stats.py's
    MIN_TRADES_FOR_HEALTH_SCORE) — no penalty without evidence, the same
    "no hallucinated data" convention used everywhere else in this codebase.
    """
    if health_score is None:
        return StrategyHealthVerdict(HEALTHY, 1.0, False)
    if health_score < HEALTH_SCORE_QUARANTINE_THRESHOLD:
        return StrategyHealthVerdict(QUARANTINED, 0.0, True)
    if health_score < DEGRADED_THRESHOLD:
        return StrategyHealthVerdict(DEGRADED, DEGRADED_SIZE_MULTIPLIER, False)
    if health_score < WARNING_THRESHOLD:
        return StrategyHealthVerdict(WARNING, 1.0, False)
    return StrategyHealthVerdict(HEALTHY, 1.0, False)
