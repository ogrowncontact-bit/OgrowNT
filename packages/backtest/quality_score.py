"""Strategy Quality Score, Status and Final Assessment — "PROMPT 7" §38-39,
§51. Builds on packages/backtest/robustness.py's 0-100 RobustnessScoreResult
(which already covers Robustness, Out-of-Sample, Cost Sensitivity, Regime
Stability and Parameter Stability from §38's component list) and adds the
two pieces robustness.py deliberately doesn't cover: raw backtest
Performance and Sample Size gating for STATUS.

§38's closing instruction -- "Não transformar isso em probabilidade de
lucro" -- is why `score` is documented as a relative evidence measure, and
why §51's wording rule is enforced structurally: FINAL_ASSESSMENT_LABELS is
a closed set, and nothing in this module ever interpolates a score into a
sentence like "82% likely to profit."
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.backtest.robustness import RobustnessScoreResult

EXPERIMENTAL = "EXPERIMENTAL"
PROMISING = "PROMISING"
VALIDATING = "VALIDATING"
ROBUST = "ROBUST"
DEGRADED = "DEGRADED"
REJECTED = "REJECTED"
QUARANTINED = "QUARANTINED"
STATUS_LABELS = (EXPERIMENTAL, PROMISING, VALIDATING, ROBUST, DEGRADED, REJECTED, QUARANTINED)

ASSESSMENT_ROBUST = "ROBUST"
ASSESSMENT_PROMISING = "PROMISING"
ASSESSMENT_WEAK = "WEAK"
ASSESSMENT_UNSTABLE = "UNSTABLE"
ASSESSMENT_INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"
FINAL_ASSESSMENT_LABELS = (ASSESSMENT_ROBUST, ASSESSMENT_PROMISING, ASSESSMENT_WEAK, ASSESSMENT_UNSTABLE, ASSESSMENT_INSUFFICIENT_EVIDENCE)

PERFORMANCE_WEIGHT = 0.4
ROBUSTNESS_WEIGHT = 0.6

MIN_TRADES_FOR_VALIDATING = 10
MIN_TRADES_FOR_FULL_EVIDENCE = 30
ROBUST_SCORE_THRESHOLD = 70.0
PROMISING_SCORE_THRESHOLD = 45.0
MAX_INSUFFICIENT_COMPONENTS_FOR_FULL_EVIDENCE = 2


@dataclass(frozen=True)
class QualityScoreResult:
    score: float
    performance_score: float
    robustness: RobustnessScoreResult
    status: str
    final_assessment: str
    reasons: list[str] = field(default_factory=list)


def _performance_score(expectancy: float | None, num_trades: int) -> tuple[float, str]:
    if num_trades == 0 or expectancy is None:
        return 0.0, "no trades / no expectancy data"
    # Maps expectancy in R-multiples onto 0-100: 0R -> 50, +0.5R -> 100, -0.5R -> 0 (clamped).
    score = max(0.0, min(100.0, 50 + expectancy * 100))
    return round(score, 2), f"expectancy={expectancy}R over {num_trades} trades"


def compute_quality_score(
    *, expectancy: float | None, num_trades: int, robustness: RobustnessScoreResult, override_status: str | None = None,
) -> QualityScoreResult:
    performance_score, performance_note = _performance_score(expectancy, num_trades)
    score = round(PERFORMANCE_WEIGHT * performance_score + ROBUSTNESS_WEIGHT * robustness.score, 2)
    reasons = [performance_note, f"robustness_score={robustness.score}/100"]

    if override_status is not None:
        if override_status not in STATUS_LABELS:
            raise ValueError(f"unknown status: {override_status!r} (expected one of {STATUS_LABELS})")
        status = override_status
        reasons.append(f"status overridden to {override_status} by caller (e.g. live degradation/quarantine evidence)")
    elif num_trades < MIN_TRADES_FOR_VALIDATING:
        status = EXPERIMENTAL
        reasons.append(f"only {num_trades} trades -- below the {MIN_TRADES_FOR_VALIDATING} needed to start validating")
    elif len(robustness.insufficient_evidence) > MAX_INSUFFICIENT_COMPONENTS_FOR_FULL_EVIDENCE:
        status = VALIDATING
        reasons.append(f"{len(robustness.insufficient_evidence)} robustness components lack evidence: {robustness.insufficient_evidence}")
    elif expectancy is not None and expectancy <= 0:
        status = REJECTED
        reasons.append(f"expectancy {expectancy}R is not positive")
    elif score >= ROBUST_SCORE_THRESHOLD:
        status = ROBUST
    elif score >= PROMISING_SCORE_THRESHOLD:
        status = PROMISING
    else:
        status = REJECTED
        reasons.append(f"score {score} below the {PROMISING_SCORE_THRESHOLD} promising threshold")

    insufficient_evidence = num_trades < MIN_TRADES_FOR_FULL_EVIDENCE or len(robustness.insufficient_evidence) > MAX_INSUFFICIENT_COMPONENTS_FOR_FULL_EVIDENCE
    if insufficient_evidence:
        final_assessment = ASSESSMENT_INSUFFICIENT_EVIDENCE
    elif score >= ROBUST_SCORE_THRESHOLD:
        final_assessment = ASSESSMENT_ROBUST
    elif score >= PROMISING_SCORE_THRESHOLD:
        final_assessment = ASSESSMENT_PROMISING
    elif any(c.name == "parameter_stability" and c.score == 0 for c in robustness.components):
        final_assessment = ASSESSMENT_UNSTABLE
    else:
        final_assessment = ASSESSMENT_WEAK

    return QualityScoreResult(
        score=score, performance_score=performance_score, robustness=robustness,
        status=status, final_assessment=final_assessment, reasons=reasons,
    )
