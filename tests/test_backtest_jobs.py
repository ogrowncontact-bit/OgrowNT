from datetime import datetime, timedelta, timezone

from apps.backtest_worker.jobs import run_pending_jobs
from packages.backtest.versioning import get_code_version
from packages.shared.models import OHLCV, Asset, BacktestJob, BacktestRun, MonteCarloRun, StrategyRow, StressTestRun

TIMEFRAME = "1m"


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _strategy(db_session, code: str) -> StrategyRow:
    existing = db_session.query(StrategyRow).filter(StrategyRow.code == code).first()
    if existing is not None:
        return existing
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _insert_uptrend(db_session, asset: Asset, start: datetime, bars: int = 200) -> None:
    for i in range(bars):
        close = 100.0 * (1.004**i)
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=close * 0.999, high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high")
        )
    db_session.commit()


def _job(db_session, kind: str, payload: dict) -> BacktestJob:
    job = BacktestJob(kind=kind, payload=payload, status="queued")
    db_session.add(job)
    db_session.commit()
    return job


def test_backtest_job_creates_a_backtest_run(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "JOBBACKTEST")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    job = _job(db_session, "backtest", {
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": (start + timedelta(minutes=200)).isoformat(), "initial_capital": 10_000.0,
    })
    processed = run_pending_jobs(db_session)
    assert processed == 1
    db_session.refresh(job)
    assert job.status == "completed"
    assert job.error is None
    run = db_session.get(BacktestRun, job.result["backtest_run_id"])
    assert run is not None
    assert run.strategy_version == "1.0"
    assert run.data_version is not None  # defaults to the backtest's own data_fingerprint


def test_monte_carlo_job_persists_a_monte_carlo_run(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "JOBMC")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    backtest_job = _job(db_session, "backtest", {
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": (start + timedelta(minutes=200)).isoformat(), "initial_capital": 10_000.0,
    })
    run_pending_jobs(db_session)
    db_session.refresh(backtest_job)
    run_id = backtest_job.result["backtest_run_id"]

    mc_job = _job(db_session, "monte_carlo", {"backtest_run_id": run_id, "num_simulations": 50, "random_seed": 3})
    run_pending_jobs(db_session)
    db_session.refresh(mc_job)
    assert mc_job.status == "completed"
    mc_run = db_session.get(MonteCarloRun, mc_job.result["monte_carlo_run_id"])
    assert mc_run is not None
    assert mc_run.reference_backtest_run_id == run_id
    assert mc_run.random_seed == 3


def test_stress_test_job_persists_all_scenarios(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "JOBSTRESS")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    job = _job(db_session, "stress_test", {
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": (start + timedelta(minutes=200)).isoformat(), "initial_capital": 10_000.0,
    })
    run_pending_jobs(db_session)
    db_session.refresh(job)
    assert job.status == "completed"
    assert len(job.result["stress_test_run_ids"]) == 7  # every SCENARIOS entry
    rows = db_session.query(StressTestRun).filter(StressTestRun.id.in_(job.result["stress_test_run_ids"])).all()
    assert len(rows) == 7


def test_sensitivity_job_all_three_kinds(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "JOBSENS")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    for kind in ("cost", "slippage", "capital"):
        job = _job(db_session, "sensitivity", {
            "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
            "start_ts": start.isoformat(), "end_ts": (start + timedelta(minutes=200)).isoformat(),
            "initial_capital": 10_000.0, "kind": kind,
        })
        run_pending_jobs(db_session)
        db_session.refresh(job)
        assert job.status == "completed", job.error
        assert job.result["kind"] == kind
        assert len(job.result["points"]) > 0


def test_full_lab_job_produces_the_report(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "JOBFULLLAB")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    job = _job(db_session, "full_lab", {
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": (start + timedelta(minutes=200)).isoformat(),
        "initial_capital": 10_000.0, "monte_carlo_simulations": 50,
    })
    run_pending_jobs(db_session)
    db_session.refresh(job)
    assert job.status == "completed"
    assert job.result["blocked"] is False
    assert "final_assessment" in job.result


def test_job_with_missing_strategy_fails_gracefully_without_crashing_the_loop(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "JOBBADFOLLOWUP")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    bad_job = _job(db_session, "backtest", {"strategy_id": 999_999, "asset_id": asset.id})
    good_job = _job(db_session, "backtest", {
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": (start + timedelta(minutes=200)).isoformat(), "initial_capital": 10_000.0,
    })

    processed = run_pending_jobs(db_session, max_jobs_per_cycle=2)
    assert processed == 2
    db_session.refresh(bad_job)
    db_session.refresh(good_job)
    assert bad_job.status == "failed"
    assert "strategy_id" in bad_job.error
    # One job's failure must never block the next one in the same poll.
    assert good_job.status == "completed"


def test_jobs_processed_in_fifo_order(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "JOBFIFO")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    payload = {
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": (start + timedelta(minutes=200)).isoformat(), "initial_capital": 10_000.0,
    }
    first = _job(db_session, "backtest", payload)
    second = _job(db_session, "backtest", payload)

    processed = run_pending_jobs(db_session, max_jobs_per_cycle=1)
    assert processed == 1
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.status == "completed"
    assert second.status == "queued"


def test_code_version_is_recorded_or_honestly_none(db_session):
    strategy = _strategy(db_session, "trend_following_v1")
    asset = _asset(db_session, "JOBCODEVER")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    job = _job(db_session, "backtest", {
        "strategy_id": strategy.id, "asset_id": asset.id, "timeframe": TIMEFRAME,
        "start_ts": start.isoformat(), "end_ts": (start + timedelta(minutes=200)).isoformat(), "initial_capital": 10_000.0,
    })
    run_pending_jobs(db_session)
    db_session.refresh(job)
    run = db_session.get(BacktestRun, job.result["backtest_run_id"])
    assert run.code_version == get_code_version()  # either a real sha or None, never a fabricated placeholder
