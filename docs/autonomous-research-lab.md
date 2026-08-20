# Autonomous Research & Evolution Engine ("PROMPT 10")

## The central constraint

> SELF-IMPROVEMENT != SELF-EXECUTION — the system can research and propose
> improvements. It cannot alter the production system directly.

Every module in `packages/research/` and `apps/research_worker/` is built
around this one rule. Nothing in this phase can promote a `StrategyVersion`
to champion, quarantine one, roll one back, or flip a `ResearchHypothesis`
to `approved` on its own — every one of those state changes runs through
`packages/research/approval.py`, which requires a non-empty human
`reviewer` string and writes an `AuditLog` row. §64's "no automatic
production promotion" is enforced structurally, the same way
`packages/agents/permissions.py` enforces the multi-agent sandbox
(`docs/multi-agent-architecture.md`) — checked by
`tests/test_research_red_team.py` on every test run, not left to
convention.

The learning loop this phase implements is a **scientific research loop**
(diagnose → hypothesis → experiment → validate → human review → new
validated version), not the anti-pattern the prompt explicitly names:
"loss → change strategy → trade → loss → change strategy."

## The research pipeline

```
StrategyPerformance (existing)      OHLCV (existing)
        |                                  |
        v                                  v
 degradation.py               ExperimentEngine (experiment.py)
 classify_degradation()      composes the SAME 8 backtest-lab
        |                     primitives run_full_lab already uses
        v                                  |
 hypothesis.py                             v
 create_hypothesis()          Experiment row, status in the closed
 (DET narrative, optional            §20 vocabulary:
  LLM enrichment, 14-day       queued/running/completed/failed/
  similarity cooldown)         rejected/promising/validating/
        |                      approved/quarantined
        v                                  |
 ResearchApproval (approval.py) <----------+
 request_approval() / record_decision()
 -- requires a human reviewer --
        |
        v
 versioning.py: create_version() -> promote_to_challenger()
 -> promote_to_champion() (or rollback() / quarantine_version())
        |
        v
 report.py::generate_research_report() -- 11-section human-facing summary
```

Every arrow above is a function call already covered by a test in
`tests/test_research_*.py`; `tests/test_research_e2e_scenario.py` runs the
whole chain once, end to end, against a real seeded dataset.

## Modules

| Module | Responsibility |
|---|---|
| `packages/research/dsl.py` | Whitelisted dict-based condition/expression tree for an experimental strategy's entry/exit logic — never Python source, never `eval`/`exec`/`compile` |
| `packages/research/significance.py` | `detect_change_point` (two-sample z-test) and `benjamini_hochberg` (multiple-testing correction) — shared statistical primitives |
| `packages/research/degradation.py` | 6-state taxonomy (HEALTHY/WATCH/DEGRADING/DEGRADED/FAILED/QUARANTINED), distinct from the live Risk Engine's 4-state gate (`packages/risk/strategy_health.py`) |
| `packages/research/hypothesis.py` + `packages/llm/hypothesis.py` | DET-first hypothesis generation with optional LLM narrative enrichment; 14-day similarity cooldown so the same research question isn't re-proposed |
| `packages/research/experiment.py` | `ExperimentEngine` — control vs candidate, composing `run_backtest`/`run_walk_forward`/`run_monte_carlo`/`run_cost_sensitivity`/`run_slippage_sensitivity`/`run_stress_scenario`/`check_parameter_stability`/`compute_robustness_score`/`compute_quality_score` (the same primitives `run_full_lab` already uses) |
| `packages/research/features.py` | Feature/regime correlation research (`PatternPerformance` reads) + `FeatureAblationStrategy` for with/without-feature A/B testing |
| `packages/research/generator.py` | `StrategyGenerator` — bounded genetic search over numeric parameters (mutation + crossover, capped at `MAX_SEARCH_EVALUATIONS`) and DSL feature-filter proposals |
| `packages/research/versioning.py` | `StrategyVersion` lifecycle (experimental/challenger/champion/production_candidate/rolled_back/retired) + Champion/Challenger + Shadow Mode |
| `packages/research/drift.py` | 5 drift types (feature/market/strategy/agent/data), each reusing existing evidence rather than a new compute engine |
| `packages/research/knowledge.py` | Knowledge graph (`ResearchKnowledgeEdge`) — auto-derived from experiment results, sample-size-weighted merge on repeat evidence |
| `packages/research/budget.py` | Rolling-window compute budget per resource type (`config/research_budget.yaml`), enforced by `spend()` before any costed job runs |
| `packages/research/approval.py` | The human approval gate — the only door between a proposal and a state change |
| `packages/research/report.py` | 11-section research report |
| `apps/research_worker/` | Third, separate process/queue (`research_queue` table) — never competes with `apps/worker`'s live trading loop or `apps/backtest_worker`'s operator-triggered Strategy Lab jobs |

## Two axes of "version"

`StrategyRow.lifecycle_stage` (Phase 2: idea → backtest → out_of_sample →
paper → small_capital → production → quarantine → retired) is the
**capital-tier promotion axis** — untouched by this phase.

`StrategyVersion.lifecycle_status` (experimental → challenger → champion →
rolled_back / retired) is an **orthogonal axis**: many versions can exist
per `strategy_id`, each independently validated
(`validation_status`, reusing `packages.backtest.quality_score`'s exact
closed STATUS_LABELS). A strategy can be in `lifecycle_stage="paper"` while
its `StrategyVersion`s cycle through champion/challenger independently.

## Shadow Mode, scoped honestly

This is a single-user, paper-trading-only system with no live capital
anywhere. Rather than building a second, parallel signal-generation
pipeline inside `apps/worker` — a genuinely new execution path the
prompt's own "self-improvement != self-execution" constraint argues
against — `versioning.run_shadow_evaluation` shadow-tests a challenger by
running the champion as control and the challenger as candidate through
the same `ExperimentEngine` this phase already built, over the most recent
real market data. Same evidence a live shadow deployment would produce,
zero new infrastructure, zero risk of ever touching a live signal path.

## Compute isolation

Three separate processes, three Dockerfiles, one shared Postgres:

- `apps/worker` — the 24/7 live scan/strategy/risk loop
- `apps/backtest_worker` — operator-triggered, on-demand Strategy Lab jobs (`backtest_jobs`)
- `apps/research_worker` — autonomous research jobs (`research_queue`)

None of the three can starve another. `apps/research_worker/jobs.py`'s
compute-costed handlers (`experiment`/`feature_test`/`strategy_test`/
`regime_test`) call `packages.research.budget.spend` before doing any
work, raising `BudgetExceededError` rather than letting a runaway search
burn unbounded compute.

## API and dashboard

`GET/POST /api/research-lab/*` (`apps/api/routers/research_lab.py`) —
deliberately a different prefix from the older `/api/research`
(Phase 5's `LearnedRule` endpoints, a narrower and unrelated concept).
Every `GET` is read-only; the only mutations are `POST /approvals`,
`POST /approvals/{id}/decide`, and `POST /queue`, all admin-only (RBAC).
`decide` is the *only* endpoint in this router that can ever change a
`StrategyVersion`'s lifecycle or a `ResearchHypothesis`'s status.

The dashboard's "Autonomous Research Lab" panel
(`components/AutonomousResearchLab.tsx`) renders the full 11-section
report from one `GET /api/research-lab/report` call, with inline
Approve/Reject/More-Tests buttons on pending approvals
(`ApprovalDecisionButtons.tsx`) that go through the same human-reviewer-
required workflow the API enforces server-side.

## Testing

`tests/test_research_*.py` — unit coverage for every module above,
`test_research_dsl_sandbox.py` (structural AST proof: no eval/exec/compile
anywhere in the research pipeline, no reach into `packages.execution`),
`test_research_red_team.py` (10-item adversarial battery targeting the
self-improvement/self-execution boundary specifically), and
`test_research_e2e_scenario.py` (the full diagnose → hypothesis →
experiment → validate → human-review → promote → rollback loop, against a
real seeded dataset).
