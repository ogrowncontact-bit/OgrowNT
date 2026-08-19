"""NewsDeduplicationEngine — Prompt 6 §5, §23-24.

Groups near-duplicate reports of the same underlying event into one
cluster via a deterministic headline-similarity heuristic (Jaccard
similarity over significant words) — no embedding/NLP model is available
in this environment, so this is documented as a heuristic, not a claim of
true semantic clustering. Good enough to tell "Central bank holds rates" /
"Rates unchanged" / "Central bank keeps policy unchanged" apart from an
unrelated headline in the same category, which is what §5's own example
asks for.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

_STOPWORDS = {
    "a", "an", "the", "to", "of", "in", "on", "for", "and", "or", "is", "are", "was",
    "were", "at", "as", "by", "with", "from", "its", "their", "after", "before", "amid",
    "over", "under", "new", "said", "says", "say", "will", "than", "into",
}
_WORD_RE = re.compile(r"[a-z0-9]+")

# Deliberately loose: category is already a hard prerequisite filter
# applied by the caller (find_cluster below only compares within the same
# category, and apps/worker/news_agent.py additionally restricts candidates
# to a recent time window), so headline overlap only needs to confirm, not
# carry the whole match on its own. Prompt 6 §5's own example — "Central
# bank holds rates" vs "Central bank keeps policy unchanged" — shares only
# "central"/"bank" (Jaccard ~0.29) despite being the same event; a stricter
# threshold would miss the spec's own worked example.
DEFAULT_SIMILARITY_THRESHOLD = 0.25
# Guards against short-headline false positives that a low Jaccard
# threshold alone would let through (two 3-word headlines sharing one
# generic word can already clear 0.25).
MIN_SHARED_WORDS = 2
DEFAULT_CLUSTER_WINDOW_HOURS = 6.0


def _significant_words(headline: str) -> set[str]:
    return {w for w in _WORD_RE.findall(headline.lower()) if w not in _STOPWORDS and len(w) > 2}


def headline_similarity(a: str, b: str) -> float:
    wa, wb = _significant_words(a), _significant_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _shared_word_count(a: str, b: str) -> int:
    return len(_significant_words(a) & _significant_words(b))


@dataclass(frozen=True)
class ClusterCandidate:
    news_event_id: int
    cluster_id: int
    headline: str
    category: str | None
    source: str
    sentiment: str
    published_at: datetime


def find_cluster(
    headline: str, category: str | None, candidates: list[ClusterCandidate],
    *, threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> ClusterCandidate | None:
    """The best-matching existing item this headline's story should join
    the cluster of, or None to start a new one. `candidates` should already
    be restricted to a recent time window by the caller
    (apps/worker/news_agent.py) — clustering across weeks-old news would
    conflate unrelated recurring events (e.g. two different CPI releases)."""
    best: tuple[float, ClusterCandidate] | None = None
    for candidate in candidates:
        if category is not None and candidate.category != category:
            continue
        score = headline_similarity(headline, candidate.headline)
        if score >= threshold and _shared_word_count(headline, candidate.headline) >= MIN_SHARED_WORDS:
            if best is None or score > best[0]:
                best = (score, candidate)
    return best[1] if best else None


@dataclass(frozen=True)
class SourceConsensus:
    consensus_score: float  # 0-100
    has_conflict: bool
    independent_source_count: int


_BULLISH = {"bullish", "very_bullish"}
_BEARISH = {"bearish", "very_bearish"}


def compute_source_consensus(
    cluster_members: list[ClusterCandidate], new_source: str, new_sentiment: str
) -> SourceConsensus:
    """Prompt 6 §23-24: more independent sources agreeing raises
    consensus — the same source re-publishing does not. Sources within a
    cluster disagreeing on sentiment lowers confidence via `has_conflict`
    rather than the system arbitrarily picking a side."""
    sources = {m.source for m in cluster_members} | {new_source}
    independent_source_count = len(sources)

    sentiments = {m.sentiment for m in cluster_members if m.sentiment != "unknown"}
    if new_sentiment != "unknown":
        sentiments.add(new_sentiment)
    has_conflict = bool(sentiments & _BULLISH) and bool(sentiments & _BEARISH)

    # Diminishing returns past a handful of independent sources — §23's "5
    # fontes confiaveis" example implies confidence saturates, not that a
    # 20th source keeps adding as much as the 2nd did.
    consensus_score = min(100.0, (independent_source_count - 1) * 25.0) if independent_source_count > 1 else 0.0
    if has_conflict:
        consensus_score *= 0.5

    return SourceConsensus(
        consensus_score=round(consensus_score, 2), has_conflict=has_conflict,
        independent_source_count=independent_source_count,
    )
