from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# repo_root/config/risk_limits.yaml — see docs/blueprint/08-risk-engine.md
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "risk_limits.yaml"


@dataclass(frozen=True)
class CapitalConfig:
    initial_paper_capital: float


@dataclass(frozen=True)
class PerTradeConfig:
    max_risk_pct: float
    min_risk_reward: float


@dataclass(frozen=True)
class PortfolioLimitsConfig:
    max_exposure_pct: float
    max_single_asset_pct: float
    max_correlated_cluster_pct: float
    correlation_threshold: float


@dataclass(frozen=True)
class LossLimitsConfig:
    max_daily_loss_pct: float
    max_weekly_loss_pct: float
    max_strategy_drawdown_pct: float
    max_portfolio_drawdown_pct: float


@dataclass(frozen=True)
class LiquidityConfig:
    max_spread_bps: float
    min_orderbook_depth_multiple: float


@dataclass(frozen=True)
class DataQualityConfig:
    max_staleness_seconds: float


@dataclass(frozen=True)
class RiskLimits:
    capital: CapitalConfig
    per_trade: PerTradeConfig
    portfolio: PortfolioLimitsConfig
    loss_limits: LossLimitsConfig
    liquidity: LiquidityConfig
    data_quality: DataQualityConfig


def load_risk_limits(path: Path = CONFIG_PATH) -> RiskLimits:
    raw = yaml.safe_load(path.read_text())
    return RiskLimits(
        capital=CapitalConfig(**raw["capital"]),
        per_trade=PerTradeConfig(**raw["per_trade"]),
        portfolio=PortfolioLimitsConfig(**raw["portfolio"]),
        loss_limits=LossLimitsConfig(**raw["loss_limits"]),
        liquidity=LiquidityConfig(**raw["liquidity"]),
        data_quality=DataQualityConfig(**raw["data_quality"]),
    )
