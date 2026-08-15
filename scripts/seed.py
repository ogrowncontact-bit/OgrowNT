"""Seed script — Phase 1.

Creates the admin user (from ADMIN_EMAIL/ADMIN_PASSWORD), the initial MVP
asset universe (20-50 assets per docs/blueprint/00-overview.md), and the
starting paper portfolio snapshot (EUR 10,000, no positions).

Idempotent: safe to re-run, existing rows are left untouched.

Usage: python -m scripts.seed
"""
from __future__ import annotations

from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.db import SessionLocal
from packages.shared.logging import configure_logging
from packages.shared.models import AdminUser, Asset, PortfolioSnapshot, SystemState
from packages.shared.settings import get_settings

logger = configure_logging("seed")

# Initial MVP universe — docs/blueprint/00-overview.md §MVP (20-50 assets).
# symbol, asset_class, exchange
ASSET_UNIVERSE = [
    # crypto
    ("BTCUSDT", "crypto", "binance"),
    ("ETHUSDT", "crypto", "binance"),
    ("SOLUSDT", "crypto", "binance"),
    ("BNBUSDT", "crypto", "binance"),
    # forex
    ("EURUSD", "forex", "oanda"),
    ("GBPUSD", "forex", "oanda"),
    ("USDJPY", "forex", "oanda"),
    ("USDCHF", "forex", "oanda"),
    ("AUDUSD", "forex", "oanda"),
    # equities (large caps as a starting sample)
    ("AAPL", "equity", "nasdaq"),
    ("MSFT", "equity", "nasdaq"),
    ("NVDA", "equity", "nasdaq"),
    ("AMZN", "equity", "nasdaq"),
    ("GOOGL", "equity", "nasdaq"),
    ("TSLA", "equity", "nasdaq"),
    # indices
    ("SPX", "index", "cme"),
    ("NDX", "index", "cme"),
    ("DAX", "index", "eurex"),
    ("IBEX", "index", "bme"),
    # commodities
    ("XAU", "commodity", "comex"),
    ("XAG", "commodity", "comex"),
    ("WTI", "commodity", "nymex"),
]


def seed_admin(db) -> None:
    settings = get_settings()
    existing = db.query(AdminUser).filter(AdminUser.email == settings.admin_email).first()
    if existing:
        logger.info("Admin user already exists: %s", settings.admin_email)
        return
    admin = AdminUser(email=settings.admin_email, hashed_password=hash_password(settings.admin_password))
    db.add(admin)
    logger.info("Created admin user: %s", settings.admin_email)


def seed_assets(db) -> None:
    existing_symbols = {a.symbol for a in db.query(Asset.symbol).all()}
    created = 0
    for symbol, asset_class, exchange in ASSET_UNIVERSE:
        if symbol in existing_symbols:
            continue
        db.add(Asset(symbol=symbol, asset_class=asset_class, exchange=exchange, is_active=True))
        created += 1
    logger.info("Seeded %d new assets (%d already present)", created, len(existing_symbols))


def seed_system_state(db) -> None:
    if db.get(SystemState, True) is not None:
        return
    db.add(SystemState(id=True, safety_belt_level="normal", trading_enabled=True))
    logger.info("Initialized system_state")


def seed_portfolio(db) -> None:
    settings = get_settings()
    if db.query(PortfolioSnapshot).count() > 0:
        logger.info("Portfolio snapshots already exist, skipping")
        return
    capital = settings.initial_paper_capital
    db.add(
        PortfolioSnapshot(
            ts=datetime.now(timezone.utc),
            equity=capital,
            cash=capital,
            exposure_pct=0.0,
            daily_pnl=0.0,
            drawdown_pct=0.0,
            safety_belt_level="normal",
        )
    )
    logger.info("Seeded initial paper portfolio: EUR %.2f", capital)


def main() -> None:
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_assets(db)
        seed_system_state(db)
        seed_portfolio(db)
        db.commit()
        logger.info("Seed complete")
    finally:
        db.close()


if __name__ == "__main__":
    main()
