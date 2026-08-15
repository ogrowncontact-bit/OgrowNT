from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    asset_class: str
    exchange: str | None
    is_active: bool


class AssetCreate(BaseModel):
    symbol: str
    asset_class: str
    exchange: str | None = None
    base_currency: str | None = None
    quote_currency: str | None = None


class AssetUpdate(BaseModel):
    is_active: bool


class CandleOut(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    data_quality: str


class ComponentHealth(BaseModel):
    name: str
    status: str  # "green" | "yellow" | "red"
    detail: str | None = None


class HealthResponse(BaseModel):
    overall: str  # "green" | "degraded"
    components: list[ComponentHealth]


class SystemStatusResponse(BaseModel):
    safety_belt_level: str
    trading_enabled: bool
    updated_at: datetime
    updated_reason: str | None


class PortfolioResponse(BaseModel):
    equity: float
    cash: float
    exposure_pct: float
    daily_pnl: float
    drawdown_pct: float
    safety_belt_level: str
    as_of: datetime


class PortfolioSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ts: datetime
    equity: float
    cash: float
    exposure_pct: float
    daily_pnl: float
    drawdown_pct: float
    safety_belt_level: str


# --- Phase 2 ---------------------------------------------------------------


class StrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    family: str
    version: str
    lifecycle_stage: str


class StrategyPerformanceOut(BaseModel):
    strategy_id: int
    total_trades: int
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    note: str


class RegimeOut(BaseModel):
    asset_symbol: str
    timeframe: str
    ts: datetime
    regime: str
    confidence: float
    features: dict


class OpportunityOut(BaseModel):
    signal_id: int
    asset_symbol: str
    strategy_code: str
    strategy_name: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float | None
    risk_reward: float
    regime: str
    final_score: float
    tier: str
    ts: datetime


class ScoreBreakdown(BaseModel):
    technical: float
    pattern: float
    regime_fit: float
    historical_edge: float
    liquidity: float
    news: float
    risk_reward: float
    strategy_performance: float
    volatility_penalty: float
    correlation_penalty: float
    execution_cost_penalty: float
    drawdown_penalty: float
    final_score: float
    tier: str
    notes: dict


class OpportunityDetailOut(BaseModel):
    signal_id: int
    asset_symbol: str
    strategy_code: str
    strategy_name: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float | None
    risk_reward: float
    regime: str
    regime_confidence: float
    status: str
    ts: datetime
    score: ScoreBreakdown
