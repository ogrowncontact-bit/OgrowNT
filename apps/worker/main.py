"""Worker entrypoint — the 24/7 loop's Phase 1 slice.

Runs the Market Data Agent on a fixed interval (SCAN_INTERVAL_SECONDS). The
full Decision Pipeline (regime -> patterns -> strategies -> scoring -> risk ->
execution, docs/blueprint/05-event-flow.md) is added incrementally in later
phases; Phase 1 only proves the loop runs, connects to real (or mock) market
data, and stores it.
"""
from __future__ import annotations

import signal
import time

from apps.worker.scanner import run_scan_cycle
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
        "Worker starting — provider=%s interval=%ss", provider.name, settings.scan_interval_seconds
    )

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    while _running:
        cycle_start = time.monotonic()
        db = SessionLocal()
        try:
            run_scan_cycle(db, provider)
        except Exception:  # noqa: BLE001 - never let one bad cycle kill the loop
            logger.exception("Scan cycle failed")
        finally:
            db.close()

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0.0, settings.scan_interval_seconds - elapsed))


if __name__ == "__main__":
    main()
