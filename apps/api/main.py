from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import assets, auth, market_data, portfolio, system
from packages.shared.logging import configure_logging

logger = configure_logging("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("OgrowNT API starting up")
    yield


app = FastAPI(
    title="OgrowNT API",
    description="Private AI quant research & paper trading system — Phase 1",
    version="0.1.0",
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


@app.get("/")
def root() -> dict:
    return {"service": "ogrownt-api", "status": "online"}
