"""Seed script — Phase 1 + Phase 2.

Creates the admin user (from ADMIN_EMAIL/ADMIN_PASSWORD), the initial MVP
asset universe (20-50 assets per docs/blueprint/00-overview.md), the starting
paper portfolio snapshot (EUR 10,000, no positions), and registers the Phase 2
strategy universe (packages/quant/strategies) in the `strategies` table.

Idempotent: safe to re-run, existing rows are left untouched.

Usage: python -m scripts.seed
"""
from __future__ import annotations

from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.quant.strategies import ALL_STRATEGIES
from packages.shared.db import SessionLocal
from packages.shared.logging import configure_logging
from packages.shared.models import AdminUser, Asset, Broker, PortfolioSnapshot, StrategyRow, SystemState
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


# "PROMPT 13" §60-62 instrument precision — illustrative, per-asset-class
# defaults (NOT real exchange-published tick/lot tables for any specific
# venue), same "clearly-labeled placeholder" convention as
# packages/backtest/execution_models.py's PROVIDER_FEE_RATES. Every asset
# class actually seeded below gets a real (non-NULL) value; a class this
# dict doesn't name stays NULL (validate_precision() honestly skips a NULL
# limit rather than inventing one — see packages/execution/instrument.py).
ASSET_CLASS_PRECISION = {
    "crypto": {"tick_size": 0.01, "step_size": 0.0001, "min_quantity": 0.0001, "min_notional": 10.0},
    "forex": {"tick_size": 0.00001, "step_size": 0.01, "min_quantity": 0.01, "min_notional": 1.0},
    "equity": {"tick_size": 0.01, "step_size": 1.0, "min_quantity": 1.0, "min_notional": 1.0},
    "index": {"tick_size": 0.01, "step_size": 0.01, "min_quantity": 0.01, "min_notional": 1.0},
    "commodity": {"tick_size": 0.01, "step_size": 0.01, "min_quantity": 0.01, "min_notional": 1.0},
}


def seed_assets(db) -> None:
    existing_symbols = {a.symbol for a in db.query(Asset.symbol).all()}
    created = 0
    for symbol, asset_class, exchange in ASSET_UNIVERSE:
        if symbol in existing_symbols:
            continue
        precision = ASSET_CLASS_PRECISION.get(asset_class, {})
        db.add(Asset(symbol=symbol, asset_class=asset_class, exchange=exchange, is_active=True, **precision))
        created += 1
    logger.info("Seeded %d new assets (%d already present)", created, len(existing_symbols))


def seed_asset_precision(db) -> None:
    """Backfills tick_size/step_size/min_quantity/min_notional on any
    pre-"PROMPT 13" asset row that predates these columns — idempotent,
    only touches rows that are still NULL."""
    updated = 0
    for asset in db.query(Asset).filter(Asset.tick_size.is_(None)).all():
        precision = ASSET_CLASS_PRECISION.get(asset.asset_class)
        if precision is None:
            continue
        for field, value in precision.items():
            setattr(asset, field, value)
        updated += 1
    if updated:
        logger.info("Backfilled instrument precision on %d existing assets", updated)


def seed_broker(db) -> None:
    """"PROMPT 13" §21-23 — the default (and, in this paper-only deployment,
    only) registered BrokerAdapter. See packages/execution/broker/registry.py."""
    if db.query(Broker).filter(Broker.name == "paper").first() is not None:
        return
    db.add(Broker(name="paper", kind="paper", status="active", is_default=True))
    logger.info("Registered default 'paper' broker")


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


def seed_strategies(db) -> None:
    existing_codes = {s.code for s in db.query(StrategyRow.code).all()}
    created = 0
    for strategy in ALL_STRATEGIES:
        if strategy.code in existing_codes:
            continue
        db.add(
            StrategyRow(
                code=strategy.code,
                name=strategy.name,
                family=strategy.family,
                version=strategy.version,
                lifecycle_stage="idea",
            )
        )
        created += 1
    logger.info("Seeded %d new strategies (%d already present)", created, len(existing_codes))


def main() -> None:
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_assets(db)
        seed_asset_precision(db)
        seed_broker(db)
        seed_system_state(db)
        seed_portfolio(db)
        seed_strategies(db)
        db.commit()
        logger.info("Seed complete")
    finally:
        db.close()


if __name__ == "__main__":
    main()
