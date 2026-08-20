"""apps/research_worker/jobs.py dispatch — "PROMPT 10" §59, §92."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.research_worker.jobs import run_pending_jobs
from packages.research import budget
from packages.shared.models import OHLCV, Asset, Experiment, ResearchQueueItem, StrategyRow


def _seed_asset(db_session, symbol: str, bars: int = 60, timeframe: str = "1h"):
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    start = datetime.now(timezone.utc) - timedelta(hours=bars)
    for i in range(bars):
        wobble = 1.0 + 0.01 * ((i * 37) % 7 - 3)
        close = 100.0 * (1.0015**i) * wobble
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=timeframe, ts=start + timedelta(hours=i), open=close * 0.998, high=close * 1.006, low=close * 0.994, close=close, volume=500.0, data_quality="high")
        )
    db_session.commit()
    return asset, start, start + timedelta(hours=bars)


def test_one_failing_job_does_not_block_the_next_job_in_the_same_cycle(db_session):
    """queue_type itself is DB-CHECK-constrained to the closed vocabulary
    every handler covers, so a real failure looks like a well-formed
    queue_type with a payload the handler can't resolve (here: a
    nonexistent asset_id) -- exactly the shape a bad enqueue request from
    the API would actually take."""
    bad = ResearchQueueItem(queue_type="regime_test", payload={"asset_id": 999999, "strategy_code": "momentum_v1", "start_ts": "2026-01-01T00:00:00+00:00", "end_ts": "2026-01-02T00:00:00+00:00"})
    db_session.add(bad)
    db_session.commit()
    good = ResearchQueueItem(
        queue_type="hypothesis",
        payload={"trigger": "manual", "problem": "worker:isolation", "observation": "obs", "evidence": {}, "use_llm": False},
    )
    db_session.add(good)
    db_session.commit()

    processed = run_pending_jobs(db_session, max_jobs_per_cycle=2)
    assert processed == 2
    assert db_session.get(ResearchQueueItem, bad.id).status == "failed"
    assert db_session.get(ResearchQueueItem, bad.id).error
    assert db_session.get(ResearchQueueItem, good.id).status == "completed"


def test_hypothesis_job_completes(db_session):
    item = ResearchQueueItem(
        queue_type="hypothesis",
        payload={"trigger": "manual", "problem": "worker:test", "observation": "obs", "evidence": {"x": 1}, "use_llm": False},
    )
    db_session.add(item)
    db_session.commit()
    processed = run_pending_jobs(db_session, max_jobs_per_cycle=1)
    assert processed == 1
    refreshed = db_session.get(ResearchQueueItem, item.id)
    assert refreshed.status == "completed"
    assert refreshed.result["created"] is True


def test_unknown_queue_type_job_fails_and_records_error(db_session):
    item = ResearchQueueItem(queue_type="strategy_test", payload={"asset_id": 999999})
    db_session.add(item)
    db_session.commit()
    processed = run_pending_jobs(db_session, max_jobs_per_cycle=1)
    assert processed == 1
    refreshed = db_session.get(ResearchQueueItem, item.id)
    assert refreshed.status == "failed"
    assert refreshed.error


def test_event_test_job_reads_existing_evidence_honestly(db_session):
    asset = Asset(symbol="WORKEREVENT", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    item = ResearchQueueItem(queue_type="event_test", payload={"event_category": "rate_decision", "asset_id": asset.id})
    db_session.add(item)
    db_session.commit()
    run_pending_jobs(db_session, max_jobs_per_cycle=1)
    refreshed = db_session.get(ResearchQueueItem, item.id)
    assert refreshed.status == "completed"
    assert refreshed.result["found"] is False  # no EventReaction row seeded


def test_regime_test_job_spends_backtest_budget(db_session):
    asset, start, end = _seed_asset(db_session, "WORKERREGIME")
    item = ResearchQueueItem(
        queue_type="regime_test",
        payload={"asset_id": asset.id, "strategy_code": "momentum_v1", "timeframe": "1h", "start_ts": start.isoformat(), "end_ts": end.isoformat()},
    )
    db_session.add(item)
    db_session.commit()
    run_pending_jobs(db_session, max_jobs_per_cycle=1)
    refreshed = db_session.get(ResearchQueueItem, item.id)
    assert refreshed.status == "completed"
    status = budget.check_budget(db_session, resource_type=budget.RESOURCE_BACKTEST)
    assert status.used == 1.0


def test_experiment_job_spends_experiment_budget(db_session):
    asset, start, end = _seed_asset(db_session, "WORKEREXPERIMENT")
    item = ResearchQueueItem(
        queue_type="experiment",
        payload={
            "asset_id": asset.id, "timeframe": "1h", "start_ts": start.isoformat(), "end_ts": end.isoformat(),
            "control": {"strategy_code": "momentum_v1", "params": {}, "label": "control"},
            "candidate": {"strategy_code": "momentum_v1", "params": {"roc_threshold": 2.5}, "label": "candidate"},
            "monte_carlo_simulations": 20,
        },
    )
    db_session.add(item)
    db_session.commit()
    run_pending_jobs(db_session, max_jobs_per_cycle=1)
    refreshed = db_session.get(ResearchQueueItem, item.id)
    assert refreshed.status == "completed"
    assert "experiment_id" in refreshed.result
    status = budget.check_budget(db_session, resource_type=budget.RESOURCE_EXPERIMENT)
    assert status.used == 1.0
    experiment = db_session.get(Experiment, refreshed.result["experiment_id"])
    assert experiment is not None


def test_knowledge_update_job_derives_edges_from_a_real_experiment(db_session):
    strategy = StrategyRow(code="worker_knowledge_v1", name="x", family="test", version="1.0")
    db_session.add(strategy)
    experiment = Experiment(
        hypothesis_id=None, type="backtest",
        control={"strategy_code": "worker_knowledge_v1", "params": {}},
        candidate={"strategy_code": "worker_knowledge_v1", "params": {"a": 1}},
        dataset={}, parameters={}, status="promising",
        result={"changed_params": ["a"], "candidate_report": {"num_trades": 20, "quality_score": 80.0}},
        reproducibility={}, created_at=datetime.now(timezone.utc),
    )
    db_session.add(experiment)
    db_session.commit()

    item = ResearchQueueItem(queue_type="knowledge_update", payload={"experiment_id": experiment.id})
    db_session.add(item)
    db_session.commit()
    run_pending_jobs(db_session, max_jobs_per_cycle=1)
    refreshed = db_session.get(ResearchQueueItem, item.id)
    assert refreshed.status == "completed"
    assert refreshed.result["edges_created_or_updated"] == 1


def test_feature_test_job_completes(db_session):
    asset, start, end = _seed_asset(db_session, "WORKERFEATURE", timeframe="15m", bars=250)
    item = ResearchQueueItem(
        queue_type="feature_test",
        payload={
            "asset_id": asset.id, "strategy_code": "momentum_v1", "feature_filter": {"gt": ["rsi_14", 50]},
            "timeframe": "15m", "start_ts": start.isoformat(), "end_ts": end.isoformat(),
        },
    )
    db_session.add(item)
    db_session.commit()
    run_pending_jobs(db_session, max_jobs_per_cycle=1)
    refreshed = db_session.get(ResearchQueueItem, item.id)
    assert refreshed.status == "completed"
    assert "reason" in refreshed.result


def test_jobs_processed_oldest_first(db_session):
    older = ResearchQueueItem(queue_type="hypothesis", payload={"trigger": "manual", "problem": "older", "observation": "o", "evidence": {}, "use_llm": False})
    db_session.add(older)
    db_session.commit()
    newer = ResearchQueueItem(queue_type="hypothesis", payload={"trigger": "manual", "problem": "newer", "observation": "o", "evidence": {}, "use_llm": False})
    db_session.add(newer)
    db_session.commit()

    run_pending_jobs(db_session, max_jobs_per_cycle=1)
    assert db_session.get(ResearchQueueItem, older.id).status == "completed"
    assert db_session.get(ResearchQueueItem, newer.id).status == "queued"
