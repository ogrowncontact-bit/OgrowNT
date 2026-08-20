""""PROMPT 10" §92 end-to-end scenario simulation: the full research loop,
diagnose -> hypothesis -> experiment -> validate -> human-review ->
promote -> rollback, wired together exactly as a real research cycle would
run it -- reusing every module built in this phase rather than mocking any
of them. Whatever real trade counts the seeded synthetic OHLCV history
produces is what's asserted against (the same honest posture as
`tests/test_backtest_lab_full_simulation.py`); what this test actually
proves is that the WIRING between diagnosis, hypothesis, experimentation,
human approval, and version promotion is correct end-to-end, and that at
no point does any of it touch a live trading table.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.research import approval, degradation, knowledge, versioning
from packages.research.experiment import ArmSpec, run_experiment
from packages.research.hypothesis import TRIGGER_STRATEGY_DEGRADATION, create_hypothesis
from packages.research.report import generate_research_report
from packages.shared.models import OHLCV, Asset, Order, Position, StrategyPerformance, StrategyRow, Trade


def _seed_asset(db_session, symbol: str, bars: int = 250, timeframe: str = "15m"):
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    start = datetime.now(timezone.utc) - timedelta(minutes=15 * bars)
    for i in range(bars):
        wobble = 1.0 + 0.01 * ((i * 37) % 7 - 3)
        close = 100.0 * (1.0015**i) * wobble
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe=timeframe, ts=start + timedelta(minutes=15 * i), open=close * 0.998,
                high=close * 1.006, low=close * 0.994, close=close, volume=500.0 + (i % 11) * 20, data_quality="high",
            )
        )
    db_session.commit()
    return asset, start, start + timedelta(minutes=15 * bars)


def test_full_research_loop_diagnose_to_promote_to_rollback(db_session):
    reviewer = "research-lead@example.com"

    # --- 1. A registered strategy, degrading in production -----------------
    strategy = StrategyRow(code="momentum_v1", name="E2E Scenario Strategy", family="momentum", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    db_session.add(
        StrategyPerformance(
            strategy_id=strategy.id, as_of=datetime.now(timezone.utc), window_trades=40, total_trades=40,
            win_rate=25.0, profit_factor=0.6, avg_win=1.0, avg_loss=-1.2, sharpe=-0.4, max_drawdown=18.0,
            expectancy=-0.25, best_regime=None, worst_regime="ranging", health_score=22.0,
        )
    )
    db_session.commit()

    # --- 2. DIAGNOSE: the Degradation Engine confirms it's genuinely unwell ---
    verdict = degradation.classify_degradation(db_session, strategy_id=strategy.id)
    assert verdict.state != degradation.DEGRADATION_STATES[0]  # not HEALTHY

    # --- 3. HYPOTHESIS: grounded in the real degradation evidence just computed ---
    hypothesis = create_hypothesis(
        db_session, trigger=TRIGGER_STRATEGY_DEGRADATION, problem=f"strategy:{strategy.code}",
        observation=f"degradation state={verdict.state}, health_score=22.0",
        evidence={"health_score": 22.0, "degradation_state": verdict.state}, assets=["E2ESCENARIO"],
        risk="medium", complexity="low", evidence_strength=0.7,
    )
    assert hypothesis is not None
    assert hypothesis.status == "proposed"
    assert hypothesis.source == TRIGGER_STRATEGY_DEGRADATION

    # --- 4. EXPERIMENT: control (current params) vs candidate (proposed change) ---
    asset, start, end = _seed_asset(db_session, "E2ESCENARIO")
    experiment = run_experiment(
        db_session, hypothesis_id=hypothesis.id, type="backtest",
        control=ArmSpec(strategy_code="momentum_v1", params={}, label="control"),
        candidate=ArmSpec(strategy_code="momentum_v1", params={"roc_threshold": 2.5}, label="candidate"),
        asset=asset, timeframe="15m", start_ts=start, end_ts=end, initial_capital=10_000.0,
        monte_carlo_simulations=30,
    )
    assert experiment.status in ("failed", "quarantined", "rejected", "promising", "validating")
    assert experiment.result is not None
    assert experiment.hypothesis_id == hypothesis.id

    # --- 5. VALIDATE: durable knowledge-graph evidence from this one experiment ---
    edges = knowledge.derive_edges_from_experiment(db_session, experiment)
    # honest either way -- a zero-trade candidate legitimately yields no edge (§ knowledge.py)
    assert isinstance(edges, list)

    # --- 6. HUMAN REVIEW: request + approve promoting the experiment's candidate ---
    promote_request = approval.request_approval(
        db_session, entity_type="experiment", entity_id=experiment.id, action="promote",
        evidence={"status": experiment.status, "hypothesis_id": hypothesis.id},
    )
    resolved_request = approval.record_decision(db_session, promote_request.id, decision="approved", reviewer=reviewer)
    assert resolved_request.status == "approved"

    from sqlalchemy import select

    from packages.shared.models import StrategyVersion

    new_version = db_session.execute(
        select(StrategyVersion).where(StrategyVersion.strategy_id == strategy.id).order_by(StrategyVersion.created_at.desc())
    ).scalars().first()
    assert new_version is not None
    assert new_version.lifecycle_status == versioning.LIFECYCLE_EXPERIMENTAL
    assert new_version.params == {"roc_threshold": 2.5}
    assert new_version.created_by == reviewer

    # --- 7. NEW VALIDATED VERSION: promote experimental -> challenger -> champion ---
    challenger_request = approval.request_approval(
        db_session, entity_type="strategy_version", entity_id=new_version.id, action="promote", evidence={}
    )
    approval.record_decision(db_session, challenger_request.id, decision="approved", reviewer=reviewer)
    assert db_session.get(StrategyVersion, new_version.id).lifecycle_status == versioning.LIFECYCLE_CHALLENGER

    champion_request = approval.request_approval(
        db_session, entity_type="strategy_version", entity_id=new_version.id, action="promote", evidence={}
    )
    approval.record_decision(db_session, champion_request.id, decision="approved", reviewer=reviewer)
    assert db_session.get(StrategyVersion, new_version.id).lifecycle_status == versioning.LIFECYCLE_CHAMPION
    assert versioning.get_champion(db_session, strategy.id).id == new_version.id

    # --- 8. ROLLBACK: a human can always undo the promotion ------------------
    baseline_version = versioning.create_version(db_session, strategy_id=strategy.id, params={}, created_by=reviewer)
    versioning.promote_to_challenger(db_session, baseline_version.id, reviewer=reviewer)
    versioning.promote_to_champion(db_session, baseline_version.id, reviewer=reviewer)  # baseline supersedes the researched version
    restored = versioning.rollback(db_session, strategy.id, reviewer=reviewer)
    assert restored.id == new_version.id  # researched version restored as champion again
    assert restored.lifecycle_status == versioning.LIFECYCLE_CHAMPION

    # --- 9. REPORT: the whole cycle is visible in one human-facing summary ---
    report = generate_research_report(db_session)
    assert report.executive_summary["total_hypotheses"] >= 1
    assert any(v["id"] == new_version.id for v in report.strategy_versions)
    hypothesis_ids_in_recent_experiments = {e["id"] for e in report.recent_experiments}
    assert experiment.id in hypothesis_ids_in_recent_experiments

    # --- 10. SELF-IMPROVEMENT != SELF-EXECUTION: never a live trading side effect ---
    assert db_session.query(Trade).count() == 0
    assert db_session.query(Position).count() == 0
    assert db_session.query(Order).count() == 0
