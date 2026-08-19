from packages.quant.news.impact_score import compute_impact_score, load_impact_weights
from packages.quant.news.importance import CRITICAL, HIGH, LOW, MEDIUM, classify_importance
from packages.quant.news.source_quality import DEFAULT_SOURCE_QUALITY, score_source


def test_critical_keyword_overrides_category():
    # Even a normally-medium category becomes CRITICAL on unambiguous
    # crisis language -- Prompt 6 §14's own "major financial institution
    # collapse" example.
    assert classify_importance("m_and_a", "Major bank collapse triggers emergency crisis talks") == CRITICAL


def test_central_bank_category_defaults_to_high():
    assert classify_importance("central_bank", "Central bank holds policy rate steady") == HIGH


def test_surprise_keyword_escalates_central_bank_to_critical():
    assert classify_importance("central_bank", "Surprise rate decision shocks markets") == CRITICAL


def test_general_commentary_is_low():
    assert classify_importance("other", "Analyst shares long-term market outlook") == LOW


def test_ma_category_is_medium_by_default():
    assert classify_importance("m_and_a", "Company announces definitive agreement to acquire smaller competitor") == MEDIUM


def test_known_wire_service_scores_higher_than_unknown_source():
    assert score_source("Reuters") > score_source("Random Blog")
    assert score_source("Random Blog") == DEFAULT_SOURCE_QUALITY


def test_impact_score_direct_high_importance_scores_higher_than_indirect_low():
    weights = load_impact_weights()
    high_direct = compute_impact_score(
        source_quality_score=90, importance="critical", is_direct=True, novelty_score=100, confidence=0.9, weights=weights,
    )
    low_indirect = compute_impact_score(
        source_quality_score=50, importance="low", is_direct=False, novelty_score=20, confidence=0.2, weights=weights,
    )
    assert high_direct > low_indirect
    assert 0.0 <= high_direct <= 100.0
    assert 0.0 <= low_indirect <= 100.0


def test_impact_score_weights_sum_to_one():
    weights = load_impact_weights()
    total = weights.source_quality + weights.importance + weights.asset_relevance + weights.novelty + weights.confidence
    assert abs(total - 1.0) < 1e-6
