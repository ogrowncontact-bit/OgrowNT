"""Statistical significance primitives — "PROMPT 10" §6, §9, §54-55."""
from __future__ import annotations

from packages.research.significance import (
    CHANGE_POINT_Z_THRESHOLD,
    MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE,
    benjamini_hochberg,
    detect_change_point,
)


def test_insufficient_sample_is_honest_not_a_guess():
    result = detect_change_point([1.0] * 5, [1.0] * 5)
    assert result.detected is False
    assert result.z_score is None
    assert "insufficient sample" in result.reason


def test_identical_distributions_detect_no_change_point():
    recent = [0.1, -0.1, 0.2, -0.2, 0.1] * (MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE // 5 + 1)
    baseline = list(recent)
    result = detect_change_point(recent[:MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE], baseline[:MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE])
    assert result.detected is False


def test_zero_pooled_variance_is_honest_not_a_division_error():
    recent = [1.0] * MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE
    baseline = [1.0] * MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE
    result = detect_change_point(recent, baseline)
    assert result.detected is False
    assert "zero pooled variance" in result.reason


def test_a_genuine_shift_is_detected():
    n = MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE
    baseline = [0.5 + 0.01 * (i % 3 - 1) for i in range(n)]
    recent = [-0.5 + 0.01 * (i % 3 - 1) for i in range(n)]
    result = detect_change_point(recent, baseline)
    assert result.detected is True
    assert abs(result.z_score) >= CHANGE_POINT_Z_THRESHOLD
    assert result.recent_mean < result.baseline_mean


def test_benjamini_hochberg_empty_input():
    assert benjamini_hochberg([]) == []


def test_benjamini_hochberg_all_significant_when_all_tiny():
    p_values = [0.001, 0.002, 0.003, 0.004]
    assert benjamini_hochberg(p_values, fdr=0.05) == [True, True, True, True]


def test_benjamini_hochberg_rejects_more_than_naive_alpha_would_survive_correction():
    """The classic textbook property: with many hypotheses tried, a raw
    p < 0.05 filter accepts more false positives than BH correction does --
    §55's exact "p-value fishing" concern. One clearly-significant p-value
    buried among many large ones should survive; the large ones should not."""
    p_values = [0.001] + [0.9] * 19
    significant = benjamini_hochberg(p_values, fdr=0.05)
    assert significant[0] is True
    assert all(s is False for s in significant[1:])


def test_benjamini_hochberg_output_length_matches_input():
    p_values = [0.01, 0.5, 0.03, 0.2, 0.8]
    assert len(benjamini_hochberg(p_values)) == len(p_values)
