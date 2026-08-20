"""ResearchQueueItem dispatch — "PROMPT 10" §59, §92. One function per
`queue_type`, called from apps/research_worker/main.py's polling loop.
Every branch is a thin adapter from a JSON payload to an already-tested
packages/research/* function, mirroring apps/backtest_worker/jobs.py's
own "no new business logic here" discipline exactly.

Compute-costed job kinds (`experiment`, `strategy_test`, `feature_test`,
`regime_test`) call `packages.research.budget.spend` BEFORE doing the
work — the research queue is where the daily research budget is actually
enforced, not merely computed. `hypothesis` only spends an `llm_call` unit
when an LLM is actually available and used; `event_test` and
`knowledge_update` are pure reads/derivations over already-computed
evidence and spend nothing.

Nothing here ever imports packages.execution's order-submission path or
touches `strategies.params`/`positions`/`orders` — every write this module
can trigger lands in Prompt 10's own tables (research_hypotheses,
experiments, strategy_versions, research_knowledge_edges,
research_budget_usage), never in a live trading table. "PROMPT 10" §57's
"self-improvement != self-execution" boundary is structural here: nothing
in this dispatch table can promote a StrategyVersion or write live
strategy params — that's packages.research.versioning, called only from a
human-initiated API request (packages/research/approval.py), never from
this queue.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.backtest.engine import run_backtest
from packages.llm.client import LLMClient
from packages.quant.strategies import STRATEGY_CLASSES
from packages.research import budget
from packages.research.events import research_event_reaction
from packages.research.experiment import ArmSpec, run_experiment
from packages.research.features import run_ablation
from packages.research.hypothesis import create_hypothesis
from packages.research.knowledge import derive_edges_from_experiment
from packages.research.versioning import run_shadow_evaluation
from packages.shared.models import Asset, ResearchQueueItem, StrategyVersion
from packages.shared.models import Experiment as ExperimentRow


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _resolve_asset(db: Session, asset_id: int) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise ValueError(f"asset_id {asset_id} not found")
    return asset


def _resolve_strategy_class(strategy_code: str):
    strategy_class = STRATEGY_CLASSES.get(strategy_code)
    if strategy_class is None:
        raise ValueError(f"unknown strategy code: {strategy_code!r}")
    return strategy_class


def _run_hypothesis_job(db: Session, payload: dict) -> dict:
    llm_client = None
    if payload.get("use_llm", True):
        candidate_client = LLMClient()
        if candidate_client.is_available():
            budget.spend(db, resource_type=budget.RESOURCE_LLM_CALL)
            llm_client = candidate_client

    hypothesis = create_hypothesis(
        db, trigger=payload["trigger"], problem=payload["problem"], observation=payload.get("observation", ""),
        evidence=payload.get("evidence", {}), assets=payload.get("assets"), timeframes=payload.get("timeframes"),
        regimes=payload.get("regimes"), risk=payload.get("risk", "medium"), complexity=payload.get("complexity", "medium"),
        evidence_strength=payload.get("evidence_strength", 0.5), llm_client=llm_client,
    )
    if hypothesis is None:
        return {"created": False, "reason": "a similar hypothesis was already proposed within the cooldown window"}
    return {"created": True, "hypothesis_id": hypothesis.id, "priority_score": hypothesis.priority_score}


def _run_experiment_job(db: Session, payload: dict) -> dict:
    asset = _resolve_asset(db, payload["asset_id"])
    budget.spend(db, resource_type=budget.RESOURCE_EXPERIMENT)
    experiment = run_experiment(
        db, hypothesis_id=payload.get("hypothesis_id"), type=payload.get("type", "backtest"),
        control=ArmSpec(**payload["control"]), candidate=ArmSpec(**payload["candidate"]),
        asset=asset, timeframe=payload.get("timeframe", "1m"),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]),
        initial_capital=payload.get("initial_capital", 10_000.0),
        **{k: payload[k] for k in ("monte_carlo_simulations", "random_seed") if k in payload},
    )
    return {"experiment_id": experiment.id, "status": experiment.status}


def _run_feature_test_job(db: Session, payload: dict) -> dict:
    asset = _resolve_asset(db, payload["asset_id"])
    strategy_class = _resolve_strategy_class(payload["strategy_code"])
    base_params = payload.get("base_params") or {}
    base_strategy = strategy_class(**base_params) if base_params else strategy_class()

    budget.spend(db, resource_type=budget.RESOURCE_BACKTEST, amount=2.0)  # run_ablation runs two backtests
    result = run_ablation(
        db, base_strategy=base_strategy, feature_filter=payload["feature_filter"], asset_id=asset.id, symbol=asset.symbol,
        timeframe=payload.get("timeframe", "1m"), start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]),
        initial_capital=payload.get("initial_capital", 10_000.0),
    )
    return {
        "adds_value": result.adds_value, "expectancy_delta": result.expectancy_delta, "reason": result.reason,
        "with_feature_trades": result.with_feature.num_trades, "without_feature_trades": result.without_feature.num_trades,
    }


def _run_strategy_test_job(db: Session, payload: dict) -> dict:
    asset = _resolve_asset(db, payload["asset_id"])
    champion = db.get(StrategyVersion, payload["champion_version_id"])
    challenger = db.get(StrategyVersion, payload["challenger_version_id"])
    if champion is None or challenger is None:
        raise ValueError("champion_version_id / challenger_version_id must reference existing strategy_versions rows")

    budget.spend(db, resource_type=budget.RESOURCE_EXPERIMENT)
    experiment = run_shadow_evaluation(
        db, champion=champion, challenger=challenger, strategy_code=payload["strategy_code"], asset=asset,
        timeframe=payload.get("timeframe", "1m"), start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]),
        initial_capital=payload.get("initial_capital", 10_000.0),
    )
    return {"experiment_id": experiment.id, "status": experiment.status}


def _run_regime_test_job(db: Session, payload: dict) -> dict:
    """Lighter-weight than `experiment`: one plain backtest's own
    `regime_breakdown` (already computed by every `run_backtest` call, see
    `packages.research.experiment.evaluate_arm`'s reuse of it), not a full
    control-vs-candidate comparison."""
    asset = _resolve_asset(db, payload["asset_id"])
    strategy_class = _resolve_strategy_class(payload["strategy_code"])
    params = payload.get("params") or {}
    strategy = strategy_class(**params) if params else strategy_class()

    budget.spend(db, resource_type=budget.RESOURCE_BACKTEST)
    result = run_backtest(
        db, strategy=strategy, asset_id=asset.id, symbol=asset.symbol, timeframe=payload.get("timeframe", "1m"),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]), initial_capital=payload.get("initial_capital", 10_000.0),
    )
    return {"num_trades": result.num_trades, "regime_breakdown": result.extra_metrics.get("regime_breakdown")}


def _run_event_test_job(db: Session, payload: dict) -> dict:
    reaction = research_event_reaction(db, event_category=payload["event_category"], asset_id=payload["asset_id"])
    if reaction is None:
        return {"found": False}
    return {
        "found": True, "sample_size": reaction.sample_size, "avg_reaction_pct": reaction.avg_reaction_pct,
        "positive_rate": reaction.positive_rate, "confidence": reaction.confidence,
    }


def _run_knowledge_update_job(db: Session, payload: dict) -> dict:
    experiment = db.get(ExperimentRow, payload["experiment_id"])
    if experiment is None:
        raise ValueError(f"experiment_id {payload['experiment_id']} not found")
    edges = derive_edges_from_experiment(db, experiment)
    return {"edges_created_or_updated": len(edges), "edge_ids": [e.id for e in edges]}


_DISPATCH = {
    "hypothesis": _run_hypothesis_job,
    "experiment": _run_experiment_job,
    "feature_test": _run_feature_test_job,
    "strategy_test": _run_strategy_test_job,
    "regime_test": _run_regime_test_job,
    "event_test": _run_event_test_job,
    "knowledge_update": _run_knowledge_update_job,
}


def run_pending_jobs(db: Session, *, max_jobs_per_cycle: int = 1) -> int:
    """Dequeues up to `max_jobs_per_cycle` QUEUED research_queue rows,
    oldest first, and executes each synchronously -- same one-at-a-time
    default and the same reasoning as
    apps/backtest_worker/jobs.py::run_pending_jobs: a private single-user
    system has no queue depth to justify parallelizing heavy research
    compute against one Postgres connection.
    """
    jobs = (
        db.query(ResearchQueueItem)
        .filter(ResearchQueueItem.status == "queued")
        .order_by(ResearchQueueItem.created_at.asc())
        .limit(max_jobs_per_cycle)
        .all()
    )
    for job in jobs:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        job_id = job.id

        handler = _DISPATCH.get(job.queue_type)
        try:
            if handler is None:
                raise ValueError(f"unknown queue_type: {job.queue_type!r}")
            result = handler(db, dict(job.payload))
            job.status = "completed"
            job.result = result
        except Exception as exc:  # noqa: BLE001 - isolate this job, keep the loop alive for the next one
            db.rollback()
            reloaded = db.get(ResearchQueueItem, job_id)
            assert reloaded is not None  # the row we just committed above can't have vanished
            job = reloaded
            job.status = "failed"
            job.error = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
    return len(jobs)
