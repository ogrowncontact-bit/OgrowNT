"""Statistical significance — "PROMPT 10" §6, §9, §54-55.

Shared primitives so degradation detection, change-point detection, and
multi-hypothesis experiment batches all use the same DET-only discipline
this codebase has used since Phase 5's research validation z-test
(`packages/quant/learning/research.py`): never react to a handful of
trades, and never accept a "significant" result from a batch of many
hypotheses without correcting for how many chances it had to look
significant by chance alone.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Same order of magnitude as packages/quant/learning/research.py's
# MIN_SAMPLE_FOR_VALIDATION (20) -- "PROMPT 10" §6's "não reagir a poucos
# trades" is the same principle applied to degradation/change-point
# comparisons instead of rule validation.
MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE = 20
# Same one-tailed 95% critical value as research.py's Z_CRITICAL (-1.645),
# used here two-tailed (a change point can be an improvement OR a decline).
CHANGE_POINT_Z_THRESHOLD = 1.645


@dataclass(frozen=True)
class ChangePointResult:
    detected: bool
    z_score: float | None
    recent_mean: float | None
    baseline_mean: float | None
    recent_n: int
    baseline_n: int
    reason: str


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _variance(values: list[float], mean_: float) -> float:
    if len(values) < 2:
        return 0.0
    return sum((v - mean_) ** 2 for v in values) / (len(values) - 1)


def detect_change_point(
    recent: list[float], baseline: list[float], *,
    min_sample: int = MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE, z_threshold: float = CHANGE_POINT_Z_THRESHOLD,
) -> ChangePointResult:
    """Two-sample z-test on the mean of `recent` vs `baseline` (e.g. R-
    multiples). Deliberately does NOT assume a decline means the strategy
    "died" (Prompt 10 §9: "Não assumir automaticamente que estratégia
    morreu") -- it only flags that behavior possibly changed; the caller
    (packages/research/degradation.py) decides what state that implies.
    """
    recent_n, baseline_n = len(recent), len(baseline)
    if recent_n < min_sample or baseline_n < min_sample:
        return ChangePointResult(
            detected=False, z_score=None, recent_mean=None, baseline_mean=None,
            recent_n=recent_n, baseline_n=baseline_n,
            reason=f"insufficient sample (recent={recent_n}, baseline={baseline_n}, need >= {min_sample} each)",
        )

    recent_mean, baseline_mean = _mean(recent), _mean(baseline)
    se = math.sqrt(_variance(recent, recent_mean) / recent_n + _variance(baseline, baseline_mean) / baseline_n)
    if se == 0:
        return ChangePointResult(
            detected=False, z_score=None, recent_mean=recent_mean, baseline_mean=baseline_mean,
            recent_n=recent_n, baseline_n=baseline_n, reason="zero pooled variance -- no meaningful comparison",
        )

    z_score = (recent_mean - baseline_mean) / se
    detected = abs(z_score) >= z_threshold
    return ChangePointResult(
        detected=detected, z_score=round(z_score, 4), recent_mean=round(recent_mean, 6), baseline_mean=round(baseline_mean, 6),
        recent_n=recent_n, baseline_n=baseline_n,
        reason="possible change point (POSSIBLE_REGIME_SHIFT)" if detected else "no statistically significant shift",
    )


def benjamini_hochberg(p_values: list[float], *, fdr: float = 0.05) -> list[bool]:
    """Benjamini-Hochberg false-discovery-rate correction — "PROMPT 10"
    §55: when many hypotheses/experiments are evaluated together, a naive
    "p < 0.05" per hypothesis accepts more false positives the more
    hypotheses are tried (p-value fishing, §55's explicit prohibition).
    Returns a same-length list of booleans: True where hypothesis i
    survives correction at the given false-discovery rate.
    """
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    largest_significant_rank = 0
    for rank, idx in enumerate(order, start=1):
        if p_values[idx] <= (rank / n) * fdr:
            largest_significant_rank = rank

    significant = [False] * n
    for rank, idx in enumerate(order, start=1):
        if rank <= largest_significant_rank:
            significant[idx] = True
    return significant
