from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import (
    assets, auth, backtests, learning, market_data, news, opportunities, patterns,
    portfolio, research, risk, strategies, system, trading,
)
from packages.shared.logging import configure_logging

logger = configure_logging("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("OgrowNT API starting up")
    yield


app = FastAPI(
    title="OgrowNT API",
    description="Private AI quant research & paper trading system — Phase 6",
    version="0.6.0",
    lifespan=lifespan,
)

# Single-user dashboard served from a known origin; tighten if deployed beyond localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(system.router)
app.include_router(assets.router)
app.include_router(market_data.router)
app.include_router(portfolio.router)
app.include_router(strategies.router)
app.include_router(opportunities.router)
app.include_router(risk.router)
app.include_router(trading.router)
app.include_router(news.router)
app.include_router(patterns.router)
app.include_router(learning.router)
app.include_router(research.router)
app.include_router(backtests.router)


@app.get("/")
def root() -> dict:
    return {"service": "ogrownt-api", "status": "online"}
