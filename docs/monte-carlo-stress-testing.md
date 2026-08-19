# Monte Carlo / Stress Testing / Risk of Ruin (Prompt 7 §24-30, §60)

## Regra fundamental

> "95th percentile drawdown: 18.4%" — isto não significa que vai acontecer.
> É uma simulação.

Nada em `packages/backtest/monte_carlo.py`, `risk_of_ruin.py` ou
`stress_test.py` produz uma previsão. Cada output é rotulado com o método e
o número de simulações, nunca apresentado como garantia.

## Monte Carlo Engine (`packages/backtest/monte_carlo.py`)

Resample dos **trades fechados** de um backtest de referência — nunca dos
dados de preço brutos (§25's quatro métodos operam todos sobre a mesma
lista `BacktestResult.trades`):

| Método | Mecanismo |
|---|---|
| `trade_reshuffling` | baralha a ordem dos mesmos trades (`random.Random.shuffle`) |
| `bootstrap` | amostra com reposição, mesmo tamanho |
| `return_perturbation` | escala a magnitude de cada P&L por um fator ~N(1, 0.15) |
| `slippage_perturbation` | subtrai um custo extra 0-0.3% do notional |
| `execution_perturbation` | zera um trade com 5% de probabilidade ("fill perdido") |

`run_monte_carlo(trades, *, initial_capital, method, num_simulations=1000,
random_seed=42, drawdown_threshold_pct=None)` — o mesmo `random_seed`
reproduz exatamente o mesmo batch (§49, testado em
`tests/test_backtest_monte_carlo.py::test_same_seed_is_reproducible`).
Output: percentis (P5/P10/P25/P50/P75/P90/P95) de `final_equity`,
`return_pct`, `max_drawdown_pct`, `losing_streak`, `recovery_duration_trades`
(medido em trades decorridos, não tempo real — uma sequência baralhada não
tem timestamps reais para "recuperar em"), `probability_of_loss`,
`probability_of_drawdown_threshold`.

Nota de correção: em `trade_reshuffling`, `final_equity` é **sempre** a
mesma em todas as simulações (a soma dos P&Ls não muda ao baralhar a
ordem) — só o drawdown/streak variam com o caminho. Testado explicitamente.

## Risk of Ruin (`packages/backtest/risk_of_ruin.py`)

Reutiliza o `bootstrap` do Monte Carlo Engine em vez de reimplementar um
simulador paralelo — risco de ruína É uma pergunta de Monte Carlo, só com
um limiar de pass/fail em vez de uma tabela de percentis. Hipóteses
documentadas explicitamente em `RiskOfRuinResult.assumptions` (§28):

1. trades resampled independentemente (sem persistência de regime);
2. sem correlação serial entre trades consecutivos;
3. horizonte de simulação = número de trades do backtest de referência;
4. é uma estimativa por simulação sobre trades passados, não uma garantia.

## Stress Testing Engine (`packages/backtest/stress_test.py`)

Sete cenários, cada um um re-run real do motor com um input concretamente
mais adverso — nunca "assumir 20% pior":

| Cenário | Mecanismo |
|---|---|
| `volatility_spike` | `SlippageModel(kind="volatility_based")` a bps mais alto |
| `liquidity_reduction` | `SlippageModel(kind="liquidity_based")` a bps mais alto |
| `spread_expansion` | `spread_bps` multiplicado |
| `slippage_increase` | `SlippageModel(kind="percentage")` a bps mais alto |
| `gap` | salto sintético de preço a meio da janela (só em memória) |
| `regime_reversal` | segunda metade da janela espelhada (uptrend → downtrend) |
| `market_crash` | declínio sustentado a substituir a cauda da janela |

**Nunca escreve em `ohlcv`**: `gap`/`regime_reversal`/`market_crash`
constroem uma lista de `Candle` inteiramente em memória
(`packages/backtest/stress_data.py`) e correm através de
`run_backtest_on_candles()` — uma variante de `run_backtest()` que aceita
candles já carregadas em vez de consultar a base de dados. Outras cadências
ao vivo (Market Scanner, Strategy Runner) leem `ohlcv` concorrentemente;
mutá-la, mesmo temporariamente, violaria "READ/COMPUTE only" (§65). Provado
em `tests/test_backtest_stress_test.py::test_market_crash_scenario_never_touches_real_ohlcv_table`.

`consecutive_losses` e `news_shock` (nomeados no §29) não estão
implementados, com razão documentada no docstring do módulo: o primeiro já
é coberto, com uma distribuição estatística real em vez de uma sequência
escolhida à mão, pelos percentis `losing_streak` do Monte Carlo Engine
acima; o segundo exigiria escrever `NewsEvent`/`NewsImpact` sintéticos na
base de dados — a mesma violação de "nunca mutar tabelas partilhadas" que
os outros três cenários evitam ficando em memória.

## Kill Switch Drill (§60)

Não é um mecanismo novo — `packages/backtest/risk.py`'s
`evaluate_signal_for_backtest()` já chama `should_trigger_kill_switch` em
cada sinal candidato desde a Phase 6. Provado de duas formas:

1. **Determinística**: um `PortfolioState` construído a 1.5x o limiar
   EMERGENCY é rejeitado com `reason == "kill_switch"`, independentemente
   da qualidade do sinal
   (`tests/test_backtest_stress_test.py::test_kill_switch_drill_blocks_new_trades_once_drawdown_crosses_threshold`).
2. **Integração**: `market_crash` corre o motor completo;
   `extra_metrics.risk_veto_counts["kill_switch"]`
   (`packages/backtest/engine.py`) conta quantas vezes o kill switch
   disparou de facto durante o run — evidência real, não uma alegação.

Limitação honesta: com posições dimensionadas a uma pequena % do capital
por trade e no máximo uma posição aberta de cada vez (arquitetura
single-asset), um único crash sintético absorvido por um stop-loss pode
legitimamente nunca atingir o limiar de drawdown de portefólio — isso é o
sistema a funcionar corretamente, não uma falha do drill.
