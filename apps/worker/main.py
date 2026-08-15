"""Worker entrypoint — the 24/7 loop.

Runs two independent cadences (docs/blueprint/05-event-flow.md §Cadência):
- Market Data Agent (scan) every SCAN_INTERVAL_SECONDS — Phase 1.
- Strategy Engine cycle every STRATEGY_INTERVAL_SECONDS — Phase 2: regime
  classification, the 4 strategies, and Opportunity Scoring, with a one-off
  history backfill per asset so new assets don't have to wait
  MIN_CANDLES_REQUIRED real minutes before strategies can run.

The full Decision Pipeline (+ Risk Engine, Execution) is added in Phase 3.
"""
from __future__ import annotations

import signal
import time

from apps.worker.history import backfill_active_assets
from apps.worker.scanner import run_scan_cycle
from apps.worker.strategy_runner import run_strategy_cycle
from packages.data.connectors.market.factory import get_market_data_provider
from packages.shared.db import SessionLocal
from packages.shared.logging import configure_logging
from packages.shared.settings import get_settings

logger = configure_logging("worker")

_running = True


def _handle_shutdown(signum, frame) -> None:  # noqa: ANN001 - signal handler signature
    global _running
    logger.info("Received signal %s, shutting down after current cycle", signum)
    _running = False


def main() -> None:
    settings = get_settings()
    provider = get_market_data_provider()
    logger.info(
        "Worker starting — provider=%s scan_interval=%ss strategy_interval=%ss",
        provider.name,
        settings.scan_interval_seconds,
        settings.strategy_interval_seconds,
    )

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    db = SessionLocal()
    try:
        backfill_active_assets(db, provider)
    except Exception:  # noqa: BLE001
        logger.exception("Initial history backfill failed")
    finally:
        db.close()

    last_strategy_run = 0.0

    while _running:
        cycle_start = time.monotonic()
        db = SessionLocal()
        try:
            run_scan_cycle(db, provider)

            if cycle_start - last_strategy_run >= settings.strategy_interval_seconds:
                backfill_active_assets(db, provider)
                run_strategy_cycle(db)
                last_strategy_run = cycle_start
        except Exception:  # noqa: BLE001 - never let one bad cycle kill the loop
            logger.exception("Worker cycle failed")
        finally:
            db.close()

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0.0, settings.scan_interval_seconds - elapsed))


if __name__ == "__main__":
    main()
