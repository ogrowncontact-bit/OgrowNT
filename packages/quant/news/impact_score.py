"""Impact Score — Prompt 6 §12: 0-100, combining source quality, event
importance, asset relevance (direct vs indirect), novelty, and the LLM
interpretation's own confidence. Weights are config-driven
(config/news_weights.yaml), the same operator-tunable pattern as
config/scoring_weights.yaml and config/risk_limits.yaml — never a
hardcoded formula.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "news_weights.yaml"

_IMPORTANCE_SCORE = {"low": 20.0, "medium": 45.0, "high": 75.0, "critical": 100.0}


@dataclass(frozen=True)
class ImpactWeights:
    source_quality: float
    importance: float
    asset_relevance: float
    novelty: float
    confidence: float


def load_impact_weights(path: Path = CONFIG_PATH) -> ImpactWeights:
    raw = yaml.safe_load(path.read_text())
    return ImpactWeights(**raw["impact_score_weights"])


def load_event_window_minutes(path: Path = CONFIG_PATH) -> tuple[int, int]:
    """(pre_event_window_minutes, post_event_window_minutes) —
    packages/risk/news_guard.py."""
    raw = yaml.safe_load(path.read_text())
    return int(raw["pre_event_window_minutes"]), int(raw["post_event_window_minutes"])


def compute_impact_score(
    *,
    source_quality_score: float,
    importance: str,
    is_direct: bool,
    novelty_score: float,
    confidence: float,
    weights: ImpactWeights | None = None,
) -> float:
    weights = weights or load_impact_weights()
    importance_score = _IMPORTANCE_SCORE.get(importance, _IMPORTANCE_SCORE["low"])
    relevance_score = 100.0 if is_direct else 40.0
    confidence_score = max(0.0, min(1.0, confidence)) * 100.0

    score = (
        weights.source_quality * source_quality_score
        + weights.importance * importance_score
        + weights.asset_relevance * relevance_score
        + weights.novelty * novelty_score
        + weights.confidence * confidence_score
    )
    return round(max(0.0, min(100.0, score)), 2)
