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
