"""Backtest Worker entrypoint — "PROMPT 7" §46-47. A separate process from
apps/worker/main.py's live-trading loop, on purpose:
docs/blueprint/01-repo-structure.md's dependency table already said
`apps/worker → todos os packages exceto packages/backtest` before this
phase existed, and that rule has a real reason behind it, not just
convention -- walk-forward optimization, Monte Carlo, and stress-test
sweeps can each trigger dozens of nested backtest re-runs (see
packages/backtest/report.py's `run_full_lab`); sharing a process with the
live scan/strategy/risk cadences would risk a heavy lab job delaying a
time-sensitive live check. Two processes, two Dockerfiles
(infra/docker/Dockerfile.worker vs Dockerfile.backtest-worker), one shared
Postgres database.

This still satisfies §47's "BacktestWorker, WalkForwardWorker,
MonteCarloWorker, StressTestWorker, OptimizationWorker" as one process
dispatching by BacktestJob.kind rather than five separate OS processes --
the same single-process/multiple-logical-workers divergence used
throughout this codebase (apps/worker/main.py's own module docstring),
applied here because five truly separate processes for a private
single-user system's on-demand batch compute would be operational
overhead with no isolation benefit five kind branches in one poll loop
don't already provide (one job's exception never blocks the next poll).

Nothing here ever reads a real broker/exchange key or submits an order —
packages/backtest and everything apps/backtest_worker/jobs.py imports is
READ/COMPUTE only (§65).
"""
from __future__ import annotations

import signal
import time

from apps.backtest_worker.jobs import run_pending_jobs
from packages.shared.db import SessionLocal
from packages.shared.logging import configure_logging
from packages.shared.settings import get_settings
from packages.shared.worker_health import record_backtest_worker_heartbeat

logger = configure_logging("backtest_worker")

_running = True


def _handle_shutdown(signum, frame) -> None:  # noqa: ANN001 - signal handler signature
    global _running
    logger.info("Received signal %s, shutting down after current cycle", signum)
    _running = False


def main() -> None:
    settings = get_settings()
    logger.info("Backtest worker starting — poll_interval=%ss", settings.backtest_job_poll_interval_seconds)

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    while _running:
        cycle_start = time.monotonic()
        db = SessionLocal()
        try:
            try:
                processed = run_pending_jobs(db)
                if processed:
                    logger.info("Processed %d backtest job(s)", processed)
            except Exception:  # noqa: BLE001 - never let one bad job kill the loop
                logger.exception("run_pending_jobs failed")
            record_backtest_worker_heartbeat(db)
        except Exception:  # noqa: BLE001
            logger.exception("Backtest worker cycle failed outside job isolation")
        finally:
            db.close()

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0.0, settings.backtest_job_poll_interval_seconds - elapsed))


if __name__ == "__main__":
    main()
