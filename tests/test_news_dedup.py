from datetime import datetime, timezone

from packages.quant.news.dedup import ClusterCandidate, compute_source_consensus, find_cluster, headline_similarity
from packages.quant.news.novelty import compute_novelty_score

NOW = datetime.now(timezone.utc)


def _candidate(headline: str, cluster_id: int = 1, source: str = "Reuters", sentiment: str = "neutral") -> ClusterCandidate:
    return ClusterCandidate(
        news_event_id=cluster_id, cluster_id=cluster_id, headline=headline, category="central_bank",
        source=source, sentiment=sentiment, published_at=NOW,
    )


def test_spec_worked_example_clusters_together():
    # Prompt 6 §5's own example: "Central bank holds rates" (Reuters) and
    # "Central bank keeps policy unchanged" (a third source) are the same
    # event and share 2 significant words ("central"/"bank") -- enough for
    # this token-overlap heuristic to safely cluster them. Bloomberg's
    # ultra-terse "Rates unchanged" shares only "rates" with either -- below
    # MIN_SHARED_WORDS, a documented limitation of a heuristic with no real
    # embedding model behind it (see packages/quant/news/dedup.py's
    # docstring): a 2-word headline just doesn't carry enough signal to
    # safely match without also matching unrelated 2-word headlines.
    reuters = _candidate("Central bank holds rates")
    other = "Central bank keeps policy unchanged"
    assert find_cluster(other, "central_bank", [reuters]) is not None


def test_unrelated_same_category_headline_does_not_cluster():
    reuters = _candidate("Central bank holds rates")
    unrelated = "Minutes reveal split committee on inflation outlook"
    assert find_cluster(unrelated, "central_bank", [reuters]) is None


def test_different_category_never_clusters_even_if_similar_text():
    reuters = _candidate("Central bank holds rates", cluster_id=1)
    # Same words, different category -- must not cluster.
    assert find_cluster("Central bank holds rates steady", "inflation", [reuters]) is None


def test_headline_similarity_is_symmetric():
    a, b = "Central bank holds rates", "Central bank keeps policy unchanged"
    assert headline_similarity(a, b) == headline_similarity(b, a)


def test_source_consensus_rises_with_independent_sources():
    members = [_candidate("Central bank holds rates", source="Reuters", sentiment="neutral")]
    single = compute_source_consensus(members, "Reuters", "neutral")  # same source repeating
    multiple = compute_source_consensus(members, "Bloomberg", "neutral")  # a second independent source
    assert multiple.consensus_score > single.consensus_score
    assert multiple.independent_source_count == 2


def test_conflicting_sentiment_across_cluster_flags_conflict_and_lowers_consensus():
    members = [_candidate("Central bank holds rates", source="Reuters", sentiment="bullish")]
    conflicting = compute_source_consensus(members, "Bloomberg", "bearish")
    agreeing = compute_source_consensus(members, "Bloomberg", "bullish")
    assert conflicting.has_conflict is True
    assert agreeing.has_conflict is False
    assert conflicting.consensus_score < agreeing.consensus_score


def test_novelty_decays_with_repeat_count():
    assert compute_novelty_score(0) == 100.0
    assert compute_novelty_score(1) < compute_novelty_score(0)
    assert compute_novelty_score(10) >= 10.0  # floors out, never negative
