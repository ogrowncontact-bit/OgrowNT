"""Research Worker entrypoint — "PROMPT 10" §59, §92. A THIRD separate
process, distinct from both apps/worker.py's live-trading loop AND
apps/backtest_worker's on-demand Strategy Lab compute -- compute isolation
cuts both ways: autonomous research must never delay a time-sensitive live
check (the reason apps/backtest_worker exists at all), and it must also
never compete with an operator's own ad-hoc Strategy Lab job for the same
Postgres connection pool / CPU (§59's explicit requirement). Three
processes, three Dockerfiles, one shared Postgres database.

Nothing here ever reads a real broker/exchange key, submits an order, or
promotes a StrategyVersion — packages/research and everything
apps/research_worker/jobs.py imports either only READS existing evidence
or writes exclusively into Prompt 10's own tables (research_hypotheses,
experiments, strategy_versions, research_knowledge_edges,
research_budget_usage). "PROMPT 10" §57's "self-improvement != self-
execution": this process can propose; it can never apply.
"""
from __future__ import annotations

import signal
import time

from apps.research_worker.jobs import run_pending_jobs
from packages.shared.db import SessionLocal
from packages.shared.logging import configure_logging
from packages.shared.settings import get_settings
from packages.shared.worker_health import record_research_worker_heartbeat

logger = configure_logging("research_worker")

_running = True


def _handle_shutdown(signum, frame) -> None:  # noqa: ANN001 - signal handler signature
    global _running
    logger.info("Received signal %s, shutting down after current cycle", signum)
    _running = False


def main() -> None:
    settings = get_settings()
    logger.info("Research worker starting — poll_interval=%ss", settings.research_job_poll_interval_seconds)

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    while _running:
        cycle_start = time.monotonic()
        db = SessionLocal()
        try:
            try:
                processed = run_pending_jobs(db)
                if processed:
                    logger.info("Processed %d research job(s)", processed)
            except Exception:  # noqa: BLE001 - never let one bad job kill the loop
                logger.exception("run_pending_jobs failed")
            record_research_worker_heartbeat(db)
        except Exception:  # noqa: BLE001
            logger.exception("Research worker cycle failed outside job isolation")
        finally:
            db.close()

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0.0, settings.research_job_poll_interval_seconds - elapsed))


if __name__ == "__main__":
    main()
