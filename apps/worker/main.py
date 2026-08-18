"""Worker entrypoint — the 24/7 loop.

Runs three independent cadences (docs/blueprint/05-event-flow.md §Cadência):
- Every SCAN_INTERVAL_SECONDS: Market Data Agent (scan), Trade Monitor
  (stop/target/thesis checks on open positions), and a safety-belt refresh —
  all need to be responsive to price moves between strategy cycles.
- Every NEWS_INTERVAL_SECONDS: News Intelligence Agent — ingest, then (only
  if ANTHROPIC_API_KEY is configured) interpret into news_impact. Runs
  before the Strategy cycle below so fresh news_impact rows are available
  when regime classification and scoring read them.
- Every STRATEGY_INTERVAL_SECONDS: history backfill for new assets, the
  Strategy Engine cycle (regime -> patterns -> strategies -> scoring), and —
  for any signal scoring "possible" or better — the Risk Engine and, if
  approved, the Execution Engine (paper only).
- Every RESEARCH_INTERVAL_SECONDS: Research Agent — proposes candidate
  learned_rules for underperforming patterns/strategies and runs the DET
  validation pass (packages/quant/learning/research.py). The Learning
  Agent's per-trade half (strategy performance, health score, quarantine,
  trade journal) runs inline in the Trade Monitor above, not on this
  cadence — it reacts to trade closes, not to a clock.
- Every ALERT_DELIVERY_INTERVAL_SECONDS: attempts delivery of any
  not-yet-delivered Alert row to whatever notification channels are
  configured (apps/worker/alerts.py) — short by default since alerts
  (kill switch, safety belt changes) are time-sensitive.

Each cadence above runs in its own try/except (apps/worker/supervisor.py's
CadenceFailureTracker) — one cadence failing doesn't skip the others in the
same iteration, and a cadence that fails CONSECUTIVE_FAILURE_ALERT_THRESHOLD
times in a row raises an Alert instead of only logging. A heartbeat is
written once per iteration regardless of any cadence's outcome, so
/api/system/health can honestly report whether this loop is actually alive
(docs/blueprint/00-overview.md's "no hallucinated data" applies to the
worker's own liveness too).

Nothing here ever reads a real broker/exchange key or sends a live order —
see docs/blueprint/12-roadmap.md, live trading is explicitly out of scope
until a strategy is validated out-of-sample (Fase 6+).
"""
from __future__ import annotations

import signal
import time

from apps.worker.alerts import run_alert_delivery_cycle
from apps.worker.history import backfill_active_assets
from apps.worker.news_agent import run_news_cycle
from apps.worker.scanner import run_scan_cycle
from apps.worker.strategy_runner import run_strategy_cycle
from apps.worker.supervisor import CadenceFailureTracker
from apps.worker.trade_monitor import run_trade_monitor_cycle
from packages.data.connectors.market.factory import get_market_data_provider
from packages.data.connectors.news.factory import get_news_provider
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.llm.client import LLMClient
from packages.notifications.dispatcher import NotificationDispatcher
from packages.quant.learning.research import run_research_cycle
from packages.risk.monitor import update_safety_belt
from packages.shared.db import SessionLocal
from packages.shared.logging import configure_logging
from packages.shared.settings import get_settings
from packages.shared.worker_health import record_heartbeat

logger = configure_logging("worker")

_running = True


def _handle_shutdown(signum, frame) -> None:  # noqa: ANN001 - signal handler signature
    global _running
    logger.info("Received signal %s, shutting down after current cycle", signum)
    _running = False


def main() -> None:
    settings = get_settings()
    provider = get_market_data_provider()
    news_provider = get_news_provider()
    llm_client = LLMClient()
    dispatcher = NotificationDispatcher()
    logger.info(
        "Worker starting — market_data=%s news=%s llm_configured=%s "
        "scan_interval=%ss news_interval=%ss strategy_interval=%ss research_interval=%ss "
        "alert_delivery_interval=%ss",
        provider.name, news_provider.name, llm_client.is_available(),
        settings.scan_interval_seconds, settings.news_interval_seconds,
        settings.strategy_interval_seconds, settings.research_interval_seconds,
        settings.alert_delivery_interval_seconds,
    )
    if not llm_client.is_available():
        logger.warning(
            "ANTHROPIC_API_KEY not set — news will be ingested but not interpreted "
            "(news_impact stays empty, pattern/news scoring inputs stay neutral)"
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

    last_news_run = 0.0
    last_strategy_run = 0.0
    last_research_run = 0.0
    last_alert_delivery_run = 0.0
    tracker = CadenceFailureTracker()

    while _running:
        cycle_start = time.monotonic()
        db = SessionLocal()
        # Paper execution provider — never a real broker/exchange adapter.
        # Built outside any cadence's try/except so a scan/monitor failure
        # can't leave later cadences in this same iteration without one.
        exec_provider = PaperExecutionProvider(db)
        try:
            try:
                run_scan_cycle(db, provider)
                run_trade_monitor_cycle(db, exec_provider, llm_client)
                update_safety_belt(db)
                tracker.record_success("scan_monitor")
            except Exception as exc:  # noqa: BLE001 - isolate this cadence, keep the others running
                logger.exception("scan_monitor cadence failed")
                tracker.record_failure(db, "scan_monitor", str(exc))

            if cycle_start - last_news_run >= settings.news_interval_seconds:
                try:
                    run_news_cycle(db, news_provider, llm_client)
                    tracker.record_success("news")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("news cadence failed")
                    tracker.record_failure(db, "news", str(exc))
                last_news_run = cycle_start

            if cycle_start - last_strategy_run >= settings.strategy_interval_seconds:
                try:
                    backfill_active_assets(db, provider)
                    run_strategy_cycle(db, provider=exec_provider)
                    tracker.record_success("strategy")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("strategy cadence failed")
                    tracker.record_failure(db, "strategy", str(exc))
                last_strategy_run = cycle_start

            if cycle_start - last_research_run >= settings.research_interval_seconds:
                try:
                    run_research_cycle(db, llm_client)
                    tracker.record_success("research")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("research cadence failed")
                    tracker.record_failure(db, "research", str(exc))
                last_research_run = cycle_start

            if cycle_start - last_alert_delivery_run >= settings.alert_delivery_interval_seconds:
                try:
                    run_alert_delivery_cycle(db, dispatcher)
                    tracker.record_success("alert_delivery")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("alert_delivery cadence failed")
                    tracker.record_failure(db, "alert_delivery", str(exc))
                last_alert_delivery_run = cycle_start

            # Written regardless of any cadence's outcome above — this proves
            # the loop itself is alive, not that everything succeeded.
            record_heartbeat(db)
        except Exception:  # noqa: BLE001 - never let anything kill the outer loop
            logger.exception("Worker cycle failed outside cadence isolation")
        finally:
            db.close()

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0.0, settings.scan_interval_seconds - elapsed))


if __name__ == "__main__":
    main()
