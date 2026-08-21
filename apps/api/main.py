from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import (
    agents,
    alerts,
    analytics,
    assets,
    auth,
    backtests,
    brokers,
    execution,
    global_market,
    learning,
    market,
    market_data,
    news,
    opportunities,
    patterns,
    portfolio,
    research,
    research_lab,
    risk,
    strategies,
    system,
    trading,
    trading_control,
)
from packages.shared.logging import configure_logging
from packages.shared.settings import get_settings

logger = configure_logging("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("OgrowNT API starting up")
    yield


app = FastAPI(
    title="OgrowNT API",
    description="Private AI quant research & paper trading system — Phase 7",
    version="0.7.0",
    lifespan=lifespan,
)

# Single-user dashboard served from a known, configured origin
# (CORS_ALLOWED_ORIGINS) — never "*". Every read/write endpoint below except
# /api/auth/login and /api/system/health requires a Bearer token anyway, but
# a wildcard origin would still let any webpage the operator's browser
# visits attempt cross-origin requests against this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_allowed_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(system.router)
app.include_router(assets.router)
app.include_router(market_data.router)
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(strategies.router)
app.include_router(opportunities.router)
app.include_router(risk.router)
app.include_router(trading.router)
app.include_router(news.router)
app.include_router(news.macro_router)
app.include_router(patterns.router)
app.include_router(learning.router)
app.include_router(research.router)
app.include_router(backtests.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(trading_control.router)
app.include_router(agents.router)
app.include_router(agents.decisions_router)
app.include_router(agents.contradictions_router)
app.include_router(research_lab.router)
app.include_router(global_market.router)
app.include_router(brokers.router)
app.include_router(execution.router)


@app.get("/")
def root() -> dict:
    return {"service": "ogrownt-api", "status": "online"}
