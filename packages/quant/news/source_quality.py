"""Source Quality — Prompt 6 §4: every ingested item gets a 0-100
SOURCE_QUALITY_SCORE. A small curated reputation table — real wire
services score higher than an unlisted source — not a live
reputation-scoring service; documented as a starting heuristic operators
can extend as real sources are added (packages/data/connectors/news).
"""
from __future__ import annotations

_KNOWN_SOURCE_QUALITY: dict[str, float] = {
    "reuters": 95.0,
    "bloomberg": 95.0,
    "associated press": 93.0,
    "ap": 93.0,
    "financial times": 90.0,
    "wall street journal": 90.0,
    "the wall street journal": 90.0,
    "marketwatch": 75.0,
    "cnbc": 78.0,
    "yahoo finance": 65.0,
}
DEFAULT_SOURCE_QUALITY = 50.0
OFFICIAL_SOURCE_QUALITY_FLOOR = 90.0


def score_source(source: str, source_type: str | None = None) -> float:
    score = _KNOWN_SOURCE_QUALITY.get(source.strip().lower(), DEFAULT_SOURCE_QUALITY)
    if source_type == "official":
        score = max(score, OFFICIAL_SOURCE_QUALITY_FLOOR)
    return score
