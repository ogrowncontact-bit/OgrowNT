# Backtest Job System / apps/backtest_worker (Prompt 7 §46-47, §64-65)

## Por que um processo separado

`docs/blueprint/01-repo-structure.md`'s tabela de dependências já dizia,
antes desta fase existir: `apps/worker → todos os packages exceto
packages/backtest`. Não é uma convenção arbitrária — walk-forward
optimization, Monte Carlo e stress-test sweeps podem disparar dezenas de
re-runs aninhados do motor de backtest (ver `packages/backtest/report.py`'s
`run_full_lab`); partilhar processo com o loop de trading ao vivo
arriscaria um job pesado atrasar um check sensível ao tempo (kill switch,
stop-loss).

Por isso `apps/backtest_worker/` é um **segundo processo**, não uma
cadência dentro de `apps/worker/main.py` — ao contrário de todas as outras
divergências "vários workers → cadências" deste projeto (Prompt 6 §37,
por exemplo). Mesmo assim, os cinco "workers" nomeados no §47
(BacktestWorker/WalkForwardWorker/MonteCarloWorker/StressTestWorker/
OptimizationWorker) são um único processo a despachar por
`BacktestJob.kind` — cinco processos OS verdadeiramente separados para
compute batch sob demanda de um sistema single-user seria overhead
operacional sem benefício de isolamento que o dispatch por `kind` já não
desse (uma exceção numa `kind` nunca bloqueia a próxima).

## Fluxo

```text
POST /api/backtests/jobs {kind, payload}
        ↓
BacktestJob (status=queued)
        ↓  (apps/backtest_worker/main.py polling, a cada backtest_job_poll_interval_seconds)
run_pending_jobs() → dispatch por kind → status=running
        ↓
packages/backtest/{engine,walkforward_optimization,monte_carlo,
                    stress_test,sensitivity,report}.py
        ↓
status=completed (result=...) ou failed (error=...)
        ↓
GET /api/backtests/jobs/{id}  (polling do dashboard)
```

Um job de cada vez por omissão (`max_jobs_per_cycle=1`,
`apps/backtest_worker/jobs.py::run_pending_jobs`) — não há razão para
paralelizar compute pesado de backtest contra uma única ligação Postgres
num sistema single-user sem profundidade de fila a justificar a
complexidade.

`kind` suportados: `backtest`, `walk_forward`, `walk_forward_optimization`,
`optimize`, `monte_carlo`, `stress_test`, `sensitivity`, `full_lab`. Os
três primeiros também têm endpoints síncronos (`POST /api/backtests`,
`/walkforward`, `/optimize`, já existentes desde a Phase 6) — normalmente
rápidos o suficiente na janela curta de dados mock deste ambiente para não
precisarem do sistema de jobs.

## Cancelamento

`POST /api/backtests/jobs/{id}/cancel` só funciona em `queued` — uma job
`running` já está a executar sincronamente dentro de
`apps/backtest_worker`, sem interrupção a meio (a chamada ao motor por
baixo é uma função Python síncrona comum, não uma tarefa cooperativa).
Limitação honesta, documentada no docstring do endpoint, não escondida.

## Heartbeat

`SystemState.backtest_worker_last_heartbeat` — uma coluna separada do
`worker_last_heartbeat` do processo de trading ao vivo
(`packages/shared/worker_health.py`'s `record_backtest_worker_heartbeat`):
confundir os dois tornaria invisível a paragem de um processo sempre que o
outro continuasse saudável.

## Reprodutibilidade e READ/COMPUTE only

Cada `BacktestRun`/`MonteCarloRun`/`StressTestRun` criado por um job
regista `strategy_version`/`code_version`/`data_version`/`random_seed`
(§48-49) via `packages/backtest/persistence.py` — a mesma função de
persistência partilhada entre os endpoints síncronos e o dispatcher de
jobs, para nunca haver duas formas de decidir o que fica gravado.

`apps/backtest_worker` nunca importa `packages.execution.adapters` nem
`packages.execution.order_manager` — verificado estruturalmente em
`tests/test_backtest_lab_full_simulation.py::test_no_live_trading_anywhere_in_the_lab_pipeline`
(AST walk sobre `packages/backtest/*.py`) e comportamentalmente (uma
execução completa de `run_full_lab` nunca insere uma linha em
`positions`/`orders`/`trades`).
