# Strategy Quality Score / Status / Reality Gap / Failure Detector (Prompt 7 §23, §38-43, §51)

## Robustness Score (`packages/backtest/robustness.py`)

0-100, oito componentes ponderados (§23's lista), **cada um contribui zero
quando não há evidência** — nunca um valor neutro/generoso por omissão
(o mesmo princípio "no hallucinated data" aplicado a scoring):

| Componente | Peso | Fonte |
|---|---|---|
| Out-of-sample | 25 | `WalkForwardOptimizationResult.oos_positive_window_ratio` |
| Parameter stability | 15 | `packages/backtest/stability.py`'s `StabilityResult.stable` |
| Drawdown | 15 | `max_drawdown_pct` vs. 15% aceitável |
| Consistency | 15 | mesma proporção de janelas OOS positivas |
| Sample size | 10 | nº de trades vs. alvo de 30 |
| Regime diversity | 10 | regimes distintos negociados / 8 conhecidos |
| Asset diversity | 5 | nº de ativos testados |
| Cost sensitivity | 5 | sobreviveu a sweeps de custo/slippage |

Não é uma probabilidade de lucro — é uma medida relativa de quanta
evidência independente suporta a estratégia ter uma edge real e duradoura.

## Strategy Quality Score + Status (`packages/backtest/quality_score.py`)

`score = 0.4 * performance_score + 0.6 * robustness.score`.
`performance_score` mapeia expectancy (R) para 0-100 (0R→50, +0.5R→100).

Status (§39, sete valores): `EXPERIMENTAL` (<10 trades) → `VALIDATING`
(muitos componentes de robustez sem evidência) → `REJECTED` (expectancy
≤0 ou score baixo) → `PROMISING`/`ROBUST` (score acima de 45/70).
`DEGRADED`/`QUARANTINED` nunca são inferidos por este módulo sozinho — só
fazem sentido com uma baseline ao vivo para degradar a partir de, por isso
entram via `override_status` (chamado por `packages/backtest/failure_detector.py`).

Final Assessment (§51, cinco valores fechados):
`ROBUST`/`PROMISING`/`WEAK`/`UNSTABLE`/`INSUFFICIENT EVIDENCE`. Nunca
"Guaranteed Profit", "Safe", ou "Will make money" — testado literalmente em
`tests/test_backtest_robustness_quality_failure.py::test_quality_score_never_uses_forbidden_wording`.

## Reality Gap Analyzer (`packages/backtest/reality_gap.py`)

Distinto de `packages/quant/learning/degradation.py`'s `check_degradation`
(que só decide "disparar um Alert agora, sim/não", com cooldown) — este
módulo devolve a comparação estruturada completa (§42):
`return_difference` (sempre `None` com nota explícita — `BacktestRun.net_return`
é uma % de retorno, `StrategyPerformance` não tem equivalente, unidades
genuinamente não comparáveis), `win_rate_difference`,
`expectancy_difference`, `drawdown_difference`, `execution_difference`
(proxy via `avg_win`).

`reference_backtest()` (a query partilhada) vive em
`packages/quant/learning/degradation.py`, não aqui:
`docs/blueprint/01-repo-structure.md`'s tabela de dependências permite
`packages/backtest → packages/quant`, nunca o inverso.

## Strategy Failure Detector (`packages/backtest/failure_detector.py`)

Consolida tudo isto num veredito, **sempre apenas consultivo** — nunca
muta `strategies.lifecycle_stage` (o mesmo padrão "DET propõe" de
`packages/quant/learning/promotion.py` e `quarantine.py`):

- `STRATEGY_REJECTED`: evidência de tempo de backtest (expectancy
  negativa, drawdown excessivo, status REJECTED, alta probabilidade de
  ruína no Monte Carlo, falhou sensitivity sweep).
- `STRATEGY_QUARANTINED`: evidência de degradação ao vivo (Reality Gap
  significativo, status DEGRADED) — só faz sentido depois de haver
  performance ao vivo para comparar.
- Rejeição sempre vence sobre quarentena quando ambas se aplicam — é a
  alegação mais forte.

## API

`GET /api/backtests/reality-gap/{strategy_id}`,
`GET /api/backtests/failure-check/{strategy_id}`,
`POST /api/backtests/compare` (tabela StrategyLab §16 — compara N backtest
runs, cada um com o seu score/status recalculado).
