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
  approved, the Execution Engine (paper only). Also refreshes the full
  pairwise correlation_matrix (packages/risk/correlation_guard.py) for the
  dashboard's Risk Heatmap — the Risk Engine's own correlation_guard check
  computes its pair fresh, so this is audit/display only.
- Every RESEARCH_INTERVAL_SECONDS: Research Agent — proposes candidate
  learned_rules for underperforming patterns/strategies and runs the DET
  validation pass (packages/quant/learning/research.py). Also runs the
  NewsLearningWorker (packages/quant/news/event_reaction.py's
  compute_event_reactions) — batch, slow-changing work grouped on the same
  cadence as Research Agent for the same reason: it reasons over data that
  only changes as slowly as trades/news close, not per scan/news tick. The
  Learning Agent's per-trade half (strategy performance, health score,
  quarantine, trade journal) runs inline in the Trade Monitor above, not on
  this cadence — it reacts to trade closes, not to a clock.
- Every MACRO_CALENDAR_INTERVAL_SECONDS: MacroCalendarWorker — ingests/
  resolves the macro economic calendar (packages/data/connectors/macro).
  Slower than news_interval_seconds since a calendar changes far less often
  than headlines do.
- Every SENTIMENT_SHIFT_INTERVAL_SECONDS: SentimentWorker — per-asset
  SENTIMENT_SHIFT detection (packages/quant/news/sentiment.py), a rollup
  over already-ingested news_events rather than per-item work, so it runs
  on its own cadence instead of inline in the News Intelligence Agent above.
- Every ALERT_DELIVERY_INTERVAL_SECONDS: attempts delivery of any
  not-yet-delivered Alert row to whatever notification channels are
  configured (apps/worker/alerts.py) — short by default since alerts
  (kill switch, safety belt changes) are time-sensitive.
- Every RECONCILIATION_INTERVAL_SECONDS: PaperReconciliationEngine
  (packages/portfolio/reconciliation.py, "PROMPT 8" §69-71) re-derives cash
  from first principles and pauses trading on any mismatch.
- Every HEALTH_SNAPSHOT_INTERVAL_SECONDS: writes a SystemHealth row
  (packages/shared/worker_health.py's record_system_health_snapshot,
  "PROMPT 8" §62-66) — a persisted history GET /api/system/health's
  on-demand view doesn't keep.

Prompt 6 §37 asks for NewsIngestionWorker / NewsAnalysisWorker /
EventDetectionWorker / SentimentWorker / MacroCalendarWorker /
NewsLearningWorker as separate processes ("não colocar tudo em um único
processo"). This codebase's established architecture (every phase so far)
is a single worker process with independent *cadences*, not one OS process
per agent — deliberately kept consistent with every other agent in this
file rather than special-cased for News Intelligence. Ingestion, DET
analysis (entities/sentiment/importance/novelty/dedup/impact score), and
event detection are one cohesive, sequential pass over the same item
(run_news_cycle/apps/worker/news_agent.py) — splitting them into separate
passes would only add redundant DB round-trips with no behavioral
difference. SentimentWorker (shift detection), MacroCalendarWorker, and
NewsLearningWorker each get their own independent cadence below, which is
the actual isolation §37 is asking for: one slow/failing agent never
blocks another.

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
from apps.worker.macro_agent import run_macro_calendar_cycle
from apps.worker.market_alerts import MarketAlertTracker
from apps.worker.news_agent import run_news_cycle
from apps.worker.scanner import run_scan_cycle
from apps.worker.sentiment_agent import run_sentiment_shift_cycle
from apps.worker.strategy_runner import run_strategy_cycle
from apps.worker.supervisor import CadenceFailureTracker
from apps.worker.trade_monitor import run_trade_monitor_cycle
from packages.data.connectors.macro.factory import get_macro_calendar_provider
from packages.data.connectors.market.factory import get_market_data_provider
from packages.data.connectors.news.factory import get_news_provider
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.llm.client import LLMClient
from packages.notifications.dispatcher import NotificationDispatcher
from packages.portfolio.reconciliation import reconcile_and_enforce
from packages.portfolio.state import refresh_snapshot
from packages.quant.learning.research import run_research_cycle
from packages.quant.news.event_reaction import compute_event_reactions
from packages.risk.correlation_guard import refresh_correlation_matrix
from packages.risk.monitor import update_safety_belt
from packages.shared.db import SessionLocal
from packages.shared.logging import configure_logging
from packages.shared.settings import get_settings
from packages.shared.worker_health import record_heartbeat, record_system_health_snapshot, record_worker_restart

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
    macro_provider = get_macro_calendar_provider()
    llm_client = LLMClient()
    dispatcher = NotificationDispatcher()
    logger.info(
        "Worker starting — market_data=%s news=%s macro=%s llm_configured=%s "
        "scan_interval=%ss news_interval=%ss strategy_interval=%ss research_interval=%ss "
        "macro_calendar_interval=%ss sentiment_shift_interval=%ss alert_delivery_interval=%ss",
        provider.name, news_provider.name, macro_provider.name, llm_client.is_available(),
        settings.scan_interval_seconds, settings.news_interval_seconds,
        settings.strategy_interval_seconds, settings.research_interval_seconds,
        settings.macro_calendar_interval_seconds, settings.sentiment_shift_interval_seconds,
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
        # "PROMPT 8" §66 crash-loop protection: every process start (a fresh
        # boot AND every Docker `restart: unless-stopped` after a crash)
        # counts here. A silently crash-looping process would otherwise
        # keep trading "on" between each near-instant restart.
        if record_worker_restart(
            db, max_restarts=settings.max_worker_restarts_per_window, window_seconds=settings.restart_window_seconds
        ):
            logger.critical(
                "Crash-loop protection triggered — trading paused after repeated worker restarts within %ss",
                settings.restart_window_seconds,
            )
    except Exception:  # noqa: BLE001
        logger.exception("Initial history backfill failed")
    finally:
        db.close()

    last_news_run = 0.0
    last_strategy_run = 0.0
    last_research_run = 0.0
    last_macro_run = 0.0
    last_sentiment_shift_run = 0.0
    last_alert_delivery_run = 0.0
    last_reconciliation_run = 0.0
    last_health_snapshot_run = 0.0
    tracker = CadenceFailureTracker()
    market_alert_tracker = MarketAlertTracker()

    while _running:
        cycle_start = time.monotonic()
        db = SessionLocal()
        # Paper execution provider — never a real broker/exchange adapter.
        # Built outside any cadence's try/except so a scan/monitor failure
        # can't leave later cadences in this same iteration without one.
        exec_provider = PaperExecutionProvider(db)
        try:
            try:
                run_scan_cycle(db, provider, market_alert_tracker)
                run_trade_monitor_cycle(db, exec_provider, llm_client)
                belt_level = update_safety_belt(db)
                # Genuinely periodic, not just fill-triggered — equity/drawdown
                # move with price even between fills, and portfolio_snapshots
                # must record the real current safety_belt_level, not the
                # refresh_snapshot() default (docs/blueprint/08-risk-engine.md).
                refresh_snapshot(db, safety_belt_level=belt_level)
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

            if cycle_start - last_macro_run >= settings.macro_calendar_interval_seconds:
                try:
                    run_macro_calendar_cycle(db, macro_provider)
                    tracker.record_success("macro_calendar")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("macro_calendar cadence failed")
                    tracker.record_failure(db, "macro_calendar", str(exc))
                last_macro_run = cycle_start

            if cycle_start - last_sentiment_shift_run >= settings.sentiment_shift_interval_seconds:
                try:
                    run_sentiment_shift_cycle(db)
                    tracker.record_success("sentiment_shift")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("sentiment_shift cadence failed")
                    tracker.record_failure(db, "sentiment_shift", str(exc))
                last_sentiment_shift_run = cycle_start

            if cycle_start - last_strategy_run >= settings.strategy_interval_seconds:
                try:
                    backfill_active_assets(db, provider)
                    run_strategy_cycle(db, provider=exec_provider)
                    # Dashboard/audit trail only (packages/risk/correlation_guard.py) —
                    # check_correlation_guard above computes fresh pairwise
                    # correlation for whatever it needs on the hot path; this
                    # persists the full matrix for the Risk Heatmap (Prompt 4 §31).
                    refresh_correlation_matrix(db)
                    tracker.record_success("strategy")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("strategy cadence failed")
                    tracker.record_failure(db, "strategy", str(exc))
                last_strategy_run = cycle_start

            if cycle_start - last_research_run >= settings.research_interval_seconds:
                try:
                    run_research_cycle(db, llm_client)
                    # NewsLearningWorker (Prompt 6 §30-32): same batch/slow
                    # cadence as Research Agent above — both reason over data
                    # that only changes as trades/news close, not per tick.
                    compute_event_reactions(db)
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

            if cycle_start - last_reconciliation_run >= settings.reconciliation_interval_seconds:
                try:
                    result = reconcile_and_enforce(db)
                    if not result.ok:
                        logger.critical("Reconciliation mismatch — trading paused: %s", result.violations)
                    tracker.record_success("reconciliation")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("reconciliation cadence failed")
                    tracker.record_failure(db, "reconciliation", str(exc))
                last_reconciliation_run = cycle_start

            if cycle_start - last_health_snapshot_run >= settings.health_snapshot_interval_seconds:
                try:
                    record_system_health_snapshot(db, cadence_failures=tracker.snapshot())
                    tracker.record_success("health_snapshot")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("health_snapshot cadence failed")
                    tracker.record_failure(db, "health_snapshot", str(exc))
                last_health_snapshot_run = cycle_start

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
