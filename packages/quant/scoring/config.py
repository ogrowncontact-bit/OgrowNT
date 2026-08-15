from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# repo_root/config/scoring_weights.yaml — see docs/blueprint/07-scoring-engine.md
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "scoring_weights.yaml"


@dataclass(frozen=True)
class Weights:
    technical: float
    pattern: float
    regime: float
    historical_edge: float
    liquidity: float
    news: float
    risk_reward: float
    strategy_performance: float


@dataclass(frozen=True)
class Penalties:
    volatility_max: float
    correlation_max: float
    execution_cost_max: float
    drawdown_max: float


@dataclass(frozen=True)
class Thresholds:
    ignore: float
    watch: float
    possible: float
    high_quality: float


@dataclass(frozen=True)
class ScoringConfig:
    weights: Weights
    penalties: Penalties
    thresholds: Thresholds


def load_scoring_config(path: Path = CONFIG_PATH) -> ScoringConfig:
    raw = yaml.safe_load(path.read_text())
    return ScoringConfig(
        weights=Weights(**raw["weights"]),
        penalties=Penalties(**raw["penalties"]),
        thresholds=Thresholds(**raw["thresholds"]),
    )
