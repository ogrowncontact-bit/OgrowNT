# Backtest Engine / Strategy Lab (Prompt 7 §1-16, §44-52, §64-66)

## Princípio fundamental

> BACKTEST PROFITABLE ≠ STRATEGY GOOD.

`packages/backtest/engine.py`'s `run_backtest()` continua a ser o núcleo
event-driven já existente (Phase 6): percorre `ohlcv` uma barra de cada vez,
`window = candles[:i+1]`, nunca uma barra futura — ver `docs/blueprint/10-backtesting-paper-trading.md`.
O Prompt 7 estende esse núcleo, não o substitui.

## O que mudou no motor

- **Execução configurável** (`packages/backtest/execution_models.py`):
  `FeeModel` (percentage/fixed/tiered/provider_specific), `SlippageModel`
  (fixed/percentage/volatility_based/liquidity_based), `LatencyModel`
  (bars de atraso sinal→execução). `ExecutionConfig()` sem argumentos
  reproduz exatamente o comportamento anterior (`packages/execution/fills.py`
  continua a ser a única fonte de verdade para a Paper Execution real —
  este módulo nunca é usado fora de `packages/backtest`).
- **Métricas enriquecidas** (`packages/backtest/metrics.py`): Sortino,
  recovery factor, gross P&L, avg win/loss, exposição média, turnover,
  detalhe de drawdown (duração, ainda-underwater), streaks, distribuição de
  trades (retornos/holding time/R:R/slippage/fees), regime breakdown —
  tudo em `BacktestResult.extra_metrics` (um bundle JSON, não ~20 colunas
  novas — ver `packages/shared/models.py`'s `BacktestRun.extra_metrics`).
- **Data Integrity Gate** (`packages/backtest/data_integrity.py`, §52):
  corre antes de qualquer backtest (candles em falta, OHLC inválido, dados
  futuros, gaps de timestamp). Crítico → `BACKTEST_BLOCKED`
  (`notes.reason == "data_integrity_blocked"`), nunca um resultado
  silenciosamente enganoso. Duplicados não são verificados: a PK
  `(asset_id, timeframe, ts)` já os torna impossíveis.
- **Look-ahead bias**: nenhum mecanismo novo — a garantia já existia
  estruturalmente (`window = candles[:i+1]`). Testado adversarialmente em
  `tests/test_backtest_v2_engine.py::test_lookahead_bias_no_future_price_changes_the_past`:
  duas séries idênticas até um corte, divergindo depois; os resultados até
  ao corte têm de ser byte-a-byte idênticos.
- **News-aware backtest** (`packages/backtest/news_replay.py`, §34):
  `news_aware=True` troca `news_signals=[]` por uma query real e
  look-ahead-safe a `news_impact` (`created_at <= as_of`, nunca
  `datetime.now()`). Honestamente esparso/vazio para janelas anteriores ao
  News Intelligence worker (Prompt 6) ter começado a correr.
- **Reprodutibilidade** (§48-49): `BacktestRun.strategy_version` (de
  `StrategyRow.version`), `code_version` (`packages/backtest/versioning.py`
  — `OGROWNT_CODE_VERSION` env var em produção, `git rev-parse` local),
  `data_version`/`data_fingerprint` (hash sha256 truncado das candles
  usadas), `random_seed` (só preenchido em runs estocásticos — Monte Carlo).

## Train / Validation / Test (§17)

`packages/backtest/split.py`'s `split_train_validation_test()` — divisão
cronológica pura (nunca baralhada), 60/20/20 por omissão. Não impõe
enforcement em tempo de query — a garantia é: nenhum código deste
repositório passa o intervalo TEST para `optimize_parameters`/
`run_walk_forward_optimization` antes da avaliação final.

## Walk-Forward Optimization (§18-19)

Três módulos distintos, cada um com um papel diferente:

| Módulo | O que faz | Quando usar |
|---|---|---|
| `packages/backtest/walkforward.py` | Parâmetros fixos, consistência ao longo de janelas | "A edge aguenta o tempo todo?" |
| `packages/backtest/optimize.py` | Grid search único, validado pelo walk-forward acima | "Qual o melhor parâmetro no período todo?" |
| `packages/backtest/walkforward_optimization.py` | TRAIN→OPTIMIZE→VALIDATION por janela, repetido | O fluxo literal do §18 |

`run_walk_forward_optimization()` nunca deixa a VALIDATION influenciar a
escolha de parâmetros — provado em
`tests/test_backtest_walkforward_optimization.py::test_validation_window_never_used_to_pick_params`
por replay: re-correr os `best_params` só no TRAIN reproduz exatamente o
`train_result` já reportado.

## Overfitting (§21-22)

`packages/backtest/overfitting.py`'s `classify_overfitting(train_return,
test_return)` — os dois exemplos do spec são testados literalmente
(`tests/test_backtest_overfitting.py`): (+80%, -3%) → `SEVERE_OVERFITTING`,
(+25%, +19%) → `MORE_ROBUST`. Nunca classifica só pelo sinal do retorno de
teste.

## Strategy Lab (dashboard)

`apps/dashboard/components/StrategyLab.tsx` — Strategy/Asset/Timeframe
(fixo em "1m", mesma razão de `RunBacktestForm.tsx`)/Period/Capital/Risk
Model → um botão "Run full lab" que cria um `BacktestJob` (`kind=full_lab`)
via `POST /api/backtests/jobs` e faz polling (`GET /api/backtests/jobs/{id}`)
até `completed`/`failed`. Renderiza as secções Backtest/Walk
Forward/Monte Carlo/Stress Test/Robustness/Final Score — o mesmo relatório
de `packages/backtest/report.py`.

## Limitações honestas

- Sem dataset histórico multi-ano: `ohlcv` só tem o que o mock market data
  provider já produziu (mesma limitação documentada em
  `packages/backtest/engine.py` desde a Phase 6).
- Survivorship bias / delisting (§54-55) e comparação entre múltiplas
  fontes de dados (§56): não implementado — este ambiente só tem um
  provider mock por ativo, sem conceito de ativo retirado de bolsa. Uma
  implementação real exigiria um segundo provider e histórico de
  delisting que simplesmente não existem aqui; documentado como limitação,
  não fabricado.
