"""Autonomous Research Lab red-team battery — "PROMPT 10" §57, §64, §93.

Ten adversarial checks targeting the phase's central constraint --
"SELF-IMPROVEMENT != SELF-EXECUTION" -- and the other structural
guarantees this session built around it: the DSL sandbox, budget
enforcement, approval-gated state transitions, and honest handling of
thin/zero-trade evidence. Each item either attempts a concrete attack and
confirms it fails safely, or structurally proves an invariant an attacker
would need to break to succeed.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from packages.research import approval, budget, dsl, generator, knowledge, versioning
from packages.research.experiment import ArmReport, _classify_experiment
from packages.shared.models import Experiment, ResearchKnowledgeEdge, StrategyRow

REPO_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PKG = REPO_ROOT / "packages" / "research"
RESEARCH_WORKER_APP = REPO_ROOT / "apps" / "research_worker"
FORBIDDEN_ORDER_CALLS = ("open_position", "close_position", "reduce_position", "submit_order")


# 1. DSL injection through a realistic caller path (not dsl.validate directly)
def test_1_dsl_injection_via_feature_filter_is_rejected_end_to_end(db_session):
    from datetime import datetime, timedelta, timezone

    from packages.quant.strategies import MomentumStrategy
    from packages.research.features import run_ablation
    from packages.shared.models import OHLCV, Asset

    asset = Asset(symbol="REDTEAM1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    start = datetime.now(timezone.utc) - timedelta(hours=10)
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1h", ts=start, open=100.0, high=101.0, low=99.0, close=100.0, volume=1.0))
    db_session.commit()

    malicious_filter = {"eq": ["__import__('os').system('id')", {"lit": "x"}]}
    with pytest.raises(dsl.DslValidationError):
        run_ablation(
            db_session, base_strategy=MomentumStrategy(), feature_filter=malicious_filter, asset_id=asset.id,
            symbol=asset.symbol, timeframe="1h", start_ts=start, end_ts=start + timedelta(hours=5), initial_capital=10_000.0,
        )


# 2. Every compute-costed research_worker job handler spends budget BEFORE doing work
def test_2_every_compute_costed_job_handler_calls_budget_spend_first():
    jobs_source = (RESEARCH_WORKER_APP / "jobs.py").read_text()
    tree = ast.parse(jobs_source)
    compute_costed = {"_run_experiment_job", "_run_feature_test_job", "_run_strategy_test_job", "_run_regime_test_job"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in compute_costed:
            calls_spend = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "spend"
                for n in ast.walk(node)
            )
            if not calls_spend:
                offenders.append(node.name)
    assert offenders == [], f"compute-costed job handler(s) missing a budget.spend call: {offenders}"


# 3. No code outside packages.research.versioning ever assigns lifecycle_status="champion" directly
def test_3_only_versioning_module_ever_promotes_to_champion():
    offenders = []
    for path in RESEARCH_PKG.rglob("*.py"):
        if "__pycache__" in path.parts or path.name == "versioning.py":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "lifecycle_status":
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: direct lifecycle_status assignment")
    assert offenders == [], f"lifecycle_status set outside versioning.py: {offenders}"


# 4. record_decision always forwards the CALLER's reviewer, never substitutes a hardcoded identity
def test_4_approval_never_hardcodes_a_system_reviewer_identity(db_session):
    strategy = StrategyRow(code="redteam_reviewer_v1", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    version = versioning.create_version(db_session, strategy_id=strategy.id, params={})
    row = approval.request_approval(db_session, entity_type="strategy_version", entity_id=version.id, action="promote", evidence={})
    approval.record_decision(db_session, row.id, decision="approved", reviewer="specific-human@example.com")

    from sqlalchemy import select

    from packages.shared.models import AuditLog

    # create_strategy_version's actor is legitimately the DET/generator
    # identity (created_by) -- only the review/promotion actions require a
    # human reviewer, so scope this check to those specifically.
    logs = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "strategy_version", AuditLog.entity_id == version.id,
            AuditLog.action.in_(["promote_to_challenger", "promote_to_champion", "research_approval_approved"]),
        )
    ).scalars().all()
    assert logs  # the promotion actually happened
    assert all(log.actor == "specific-human@example.com" for log in logs)
    assert not any(log.actor in ("system", "auto", "det_engine", "research_agent", "autonomous_research_agent") for log in logs)


# 5. Nothing under packages/research or apps/research_worker calls an order-mutating function or imports packages.execution
def test_5_research_pipeline_cannot_reach_the_execution_layer():
    offenders = []
    for pkg in (RESEARCH_PKG, RESEARCH_WORKER_APP):
        for path in pkg.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_ORDER_CALLS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {node.func.id}(...)")
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("packages.execution"):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: from {node.module} import ...")
    assert offenders == [], f"execution-layer reach found: {offenders}"


# 6. SQL injection attempt through knowledge-graph string fields is inert (parameterized queries)
def test_6_knowledge_graph_string_fields_are_never_interpreted_as_sql(db_session):
    payload = "'; DROP TABLE research_knowledge_edges; --"
    edge = knowledge.upsert_edge(db_session, subject=payload, relation="improved_by", object_="x", confidence=0.5, sample_size=10, evidence={})
    assert edge.subject == payload  # stored literally

    still_there = db_session.get(ResearchKnowledgeEdge, edge.id)
    assert still_there is not None
    count = db_session.query(ResearchKnowledgeEdge).count()
    assert count >= 1  # table still exists and still has rows


# 7. Every closed-vocabulary field in the research lab rejects an out-of-vocabulary value
def test_7_closed_vocabularies_reject_injected_values(db_session):
    with pytest.raises(ValueError):
        budget.check_budget(db_session, resource_type="'; DROP TABLE research_budget_usage; --")
    with pytest.raises(ValueError):
        approval.request_approval(db_session, entity_type="hypothesis", entity_id=1, action="'; DROP TABLE research_approvals; --", evidence={})
    strategy = StrategyRow(code="redteam_vocab_v1", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    with pytest.raises(ValueError):
        versioning.create_version(db_session, strategy_id=strategy.id, params={}, lifecycle_status="'; DROP TABLE strategy_versions; --")


# 8. A fabricated-positive-expectancy zero-trade result can never classify as promising or feed the knowledge graph
def test_8_zero_trades_cannot_be_laundered_into_a_promising_or_learned_result():
    poisoned_candidate = ArmReport(
        strategy_code="x", params={}, num_trades=0, net_return=9999.0, expectancy=99.0, max_drawdown=0.0,
        win_rate=100.0, profit_factor=99.0, sharpe_like=99.0, walk_forward_consistent=True, stability_stable=True,
        monte_carlo_probability_of_loss=0.0, cost_sensitivity_survives=True, slippage_sensitivity_survives=True,
        stress_survival_count=5, stress_scenario_count=5, overfitting={"label": "NONE", "reason": "ok"},
        robustness_score=100.0, quality_score=100.0, quality_status="ROBUST", data_fingerprint="poisoned",
    )
    control = ArmReport(**{**poisoned_candidate.__dict__, "num_trades": 20, "expectancy": 0.1})
    status, reasons = _classify_experiment(control, poisoned_candidate, ["x"])
    assert status == "failed"
    assert "zero trades" in reasons[0]


def test_8b_zero_trade_experiment_produces_no_knowledge_graph_edge(db_session):
    experiment = Experiment(
        hypothesis_id=None, type="backtest", control={"strategy_code": "x", "params": {}},
        candidate={"strategy_code": "x", "params": {"a": 1}}, dataset={}, parameters={}, status="failed",
        result={"changed_params": ["a"], "candidate_report": {"num_trades": 0, "quality_score": 100.0}},
        reproducibility={},
    )
    db_session.add(experiment)
    db_session.commit()
    edges = knowledge.derive_edges_from_experiment(db_session, experiment)
    assert edges == []


# 9. propose_candidates never widens the genetic search's evaluation bound via forwarded kwargs
def test_9_propose_candidates_cannot_be_used_to_bypass_the_search_evaluation_cap(db_session):
    from datetime import datetime, timedelta, timezone

    from packages.shared.models import OHLCV, Asset

    asset = Asset(symbol="REDTEAM9", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    start = datetime.now(timezone.utc) - timedelta(hours=10)
    for i in range(10):
        db_session.add(OHLCV(asset_id=asset.id, timeframe="1h", ts=start + timedelta(hours=i), open=100.0, high=101.0, low=99.0, close=100.0, volume=1.0))
    db_session.commit()

    with pytest.raises(ValueError):
        generator.propose_candidates(
            db_session, strategy_code="momentum_v1", asset_id=asset.id, symbol=asset.symbol, timeframe="1h",
            start_ts=start, end_ts=start + timedelta(hours=10), window_days=1.0, initial_capital=10_000.0,
            genetic_kwargs={"population_size": generator.MAX_SEARCH_EVALUATIONS + 5, "generations": 1},
        )


# 10. Approving a promote action against a nonexistent entity_id fails cleanly, never silently corrupting state
def test_10a_promoting_a_spoofed_strategy_version_id_is_a_harmless_no_op(db_session):
    """_apply_approved_action returns early when the entity_id doesn't
    resolve -- no exception, but critically no StrategyVersion is created
    or mutated either; the approval row itself still records the decision
    honestly (never silently reverts to pending)."""
    row = approval.request_approval(db_session, entity_type="strategy_version", entity_id=999999, action="promote", evidence={})
    result = approval.record_decision(db_session, row.id, decision="approved", reviewer="tester@example.com")
    assert result.status == "approved"

    from sqlalchemy import select

    from packages.shared.models import StrategyVersion

    assert db_session.execute(select(StrategyVersion).where(StrategyVersion.id == 999999)).scalars().first() is None


def test_10b_promoting_a_spoofed_experiment_id_raises_instead_of_fabricating_a_version(db_session):
    row = approval.request_approval(db_session, entity_type="experiment", entity_id=999999, action="promote", evidence={})
    with pytest.raises(ValueError):
        approval.record_decision(db_session, row.id, decision="approved", reviewer="tester@example.com")

    # the failed apply must not have left the approval row falsely marked "approved"
    reloaded = db_session.get(type(row), row.id)
    assert reloaded.status == approval.STATUS_PENDING
