"""Novelty Detection — Prompt 6 §13.

100 for a genuinely new cluster (this item starts it), decaying for each
prior repeat of the same story within the clustering window
(packages/quant/news/dedup.py) — a story repeated 5 times by 5 outlets
isn't 5 new events, and shouldn't count as 5x the impact.
"""
from __future__ import annotations

NOVELTY_DECAY_PER_REPEAT = 20.0
MIN_NOVELTY_SCORE = 10.0
MAX_NOVELTY_SCORE = 100.0


def compute_novelty_score(prior_cluster_member_count: int) -> float:
    """`prior_cluster_member_count`: how many items are already in this
    story's cluster before this one joins it (0 for a brand-new cluster,
    i.e. maximum novelty)."""
    score = MAX_NOVELTY_SCORE - NOVELTY_DECAY_PER_REPEAT * max(0, prior_cluster_member_count)
    return max(MIN_NOVELTY_SCORE, score)
