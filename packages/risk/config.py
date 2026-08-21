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
    max_strategy_allocation_pct: float


@dataclass(frozen=True)
class LossLimitsConfig:
    max_daily_loss_pct: float
    max_weekly_loss_pct: float
    max_monthly_loss_pct: float
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
class SafetyBeltMultipliersConfig:
    """Risk-per-trade multiplier applied at each Safety Belt state
    (docs/blueprint/08-risk-engine.md#risk-states-safety-belts) — field names
    match packages/risk/safety_belt.py's state constants exactly so
    policy_for() can read one via getattr(this, level) without a lookup
    table. Operator-tunable like every other number in this file (Prompt 4
    §35: "Esses valores devem ser configuráveis"), not hardcoded in Python.
    """

    normal: float
    caution: float
    defensive: float
    emergency: float
    kill_switch: float


@dataclass(frozen=True)
class NewsRiskMultipliersConfig:
    """Risk-per-trade multiplier applied at each News Risk Guard level
    (packages/risk/news_guard.py, Prompt 6 §17/§26) — field names match the
    guard's level constants exactly, same getattr()-by-level pattern as
    SafetyBeltMultipliersConfig above."""

    normal: float
    elevated: float
    high: float
    critical: float


@dataclass(frozen=True)
class LeverageConfig:
    """"PROMPT 8" §41 — explicit and configurable, but never anything other
    than 1.0 while packages/shared/models.py's SystemState.trading_mode
    can't be anything but 'paper'/'live_disabled'; see
    packages/risk/engine.py's leverage check."""

    max_leverage: float


@dataclass(frozen=True)
class LossStreakConfig:
    threshold: int
    size_multiplier_when_triggered: float


@dataclass(frozen=True)
class PositionRiskPolicyConfig:
    """"PROMPT 8" §28-30 — see packages/risk/position_policy.py. Each field
    is 'hold'|'reduce'|'close'; reduce_fraction is how much of the position
    a REDUCE action closes (the rest stays open, unchanged)."""

    regime_change: str
    news_risk: str
    portfolio_emergency: str
    reduce_fraction: float


@dataclass(frozen=True)
class DrawdownLevelConfig:
    threshold_pct: float
    response: str


@dataclass(frozen=True)
class DrawdownLevelsConfig:
    """"PROMPT 12" §10 -- see packages/risk/capital_state.py::DrawdownEngine.
    Five levels, deliberately monotonic (enforced by load_risk_limits, not
    just by convention in the YAML)."""

    level_1: DrawdownLevelConfig
    level_2: DrawdownLevelConfig
    level_3: DrawdownLevelConfig
    level_4: DrawdownLevelConfig
    level_5: DrawdownLevelConfig

    def ordered(self) -> list[DrawdownLevelConfig]:
        return [self.level_1, self.level_2, self.level_3, self.level_4, self.level_5]


@dataclass(frozen=True)
class RecoveryConfig:
    """"PROMPT 12" §61 -- DrawdownEngine's de-escalation hysteresis window."""

    cooldown_minutes: float


@dataclass(frozen=True)
class RiskLimits:
    capital: CapitalConfig
    per_trade: PerTradeConfig
    portfolio: PortfolioLimitsConfig
    loss_limits: LossLimitsConfig
    liquidity: LiquidityConfig
    data_quality: DataQualityConfig
    safety_belt_multipliers: SafetyBeltMultipliersConfig
    news_risk_multipliers: NewsRiskMultipliersConfig
    leverage: LeverageConfig
    loss_streak: LossStreakConfig
    position_risk_policy: PositionRiskPolicyConfig
    drawdown_levels: DrawdownLevelsConfig
    recovery: RecoveryConfig


def load_risk_limits(path: Path = CONFIG_PATH) -> RiskLimits:
    raw = yaml.safe_load(path.read_text())
    drawdown_levels = DrawdownLevelsConfig(
        level_1=DrawdownLevelConfig(**raw["drawdown_levels"]["level_1"]),
        level_2=DrawdownLevelConfig(**raw["drawdown_levels"]["level_2"]),
        level_3=DrawdownLevelConfig(**raw["drawdown_levels"]["level_3"]),
        level_4=DrawdownLevelConfig(**raw["drawdown_levels"]["level_4"]),
        level_5=DrawdownLevelConfig(**raw["drawdown_levels"]["level_5"]),
    )
    thresholds = [lvl.threshold_pct for lvl in drawdown_levels.ordered()]
    if thresholds != sorted(thresholds):
        raise ValueError("drawdown_levels thresholds must be strictly increasing (level_1 < level_2 < ... < level_5)")
    return RiskLimits(
        capital=CapitalConfig(**raw["capital"]),
        per_trade=PerTradeConfig(**raw["per_trade"]),
        portfolio=PortfolioLimitsConfig(**raw["portfolio"]),
        loss_limits=LossLimitsConfig(**raw["loss_limits"]),
        liquidity=LiquidityConfig(**raw["liquidity"]),
        data_quality=DataQualityConfig(**raw["data_quality"]),
        safety_belt_multipliers=SafetyBeltMultipliersConfig(**raw["safety_belt_multipliers"]),
        news_risk_multipliers=NewsRiskMultipliersConfig(**raw["news_risk_multipliers"]),
        leverage=LeverageConfig(**raw["leverage"]),
        loss_streak=LossStreakConfig(**raw["loss_streak"]),
        position_risk_policy=PositionRiskPolicyConfig(**raw["position_risk_policy"]),
        drawdown_levels=drawdown_levels,
        recovery=RecoveryConfig(**raw["recovery"]),
    )
