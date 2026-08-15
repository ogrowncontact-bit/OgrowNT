# 10 — Backtesting, Anti-Overfitting & Paper Trading

## Strategy Lifecycle

```text
IDEA → BACKTEST → OUT_OF_SAMPLE → PAPER → SMALL_CAPITAL → PRODUCTION
                                                              │
                                                    PERFORMANCE DROP
                                                              ↓
                                              WARNING → REDUCED → QUARANTINED
                                                              │
                                                     (pode ser reavaliada)
```

Persistido em `strategies.lifecycle_stage` (`02-database-schema.md`). Transições só
avançam com aprovação explícita do Risk Engine (regras estatísticas, DET) — nunca
automaticamente por uma "boa impressão" de um LLM.

## Backtest Engine

Motor próprio, orientado a eventos (evita look-ahead bias — cada estratégia só vê
dados até à barra corrente).

**Input:**
```text
Strategy, Asset(s), Date Range, Timeframe, Initial Capital, Fees, Slippage model,
Risk Parameters (usa o mesmo Risk Engine/PositionSizer da produção)
```

**Output:**
```text
Net Return, CAGR-like return, Win Rate, Profit Factor, Max Drawdown,
Average Trade, Expectancy, Number of Trades, Sharpe-like metric
```

Regra dura: **um retorno alto isolado nunca classifica uma estratégia como "boa"** —
o veredicto combina expectancy, drawdown, número de trades (significância) e
estabilidade de parâmetros.

## Anti-Overfitting

1. **Train/Test split** — parâmetros calibrados só no conjunto de treino.
2. **Out-of-sample** — validação em dados nunca vistos durante a calibração.
3. **Walk-forward** — janela desliza no tempo (treina em `T0..T1`, testa em
   `T1..T2`, avança); a estratégia só passa se a expectancy se mantém consistente
   entre janelas, não só numa janela sortuda.
4. **Parameter stability** — pequenas variações nos parâmetros não podem inverter o
   resultado (senão é overfitting a ruído, ex.: "comprar às 14:37:12 de terça-feira").
5. **Performance degradation analysis** — comparação contínua do desempenho real
   (paper/produção) vs. o esperado do backtest; divergência sustentada → warning
   automático em `strategy_performance`.

## Paper Trading

`PaperExecutionProvider` (`03-api-spec.md §Execution Adapter`) simula:
- fees (config por ativo/exchange)
- spread (a partir do orderbook real, quando disponível, senão modelo estático)
- slippage (função do tamanho da ordem vs. profundidade do livro)
- partial fills quando o tamanho excede a liquidez simulada

Conta inicial: **€10.000** (`config/risk_limits.yaml capital.initial_paper_capital`,
editável pelo painel). Todas as ordens ficam marcadas `orders.is_paper = true` — o
schema já está preparado para live trading (`is_paper = false`), mas **nenhum
adapter real é instanciado no MVP** (`04-agents-architecture.md`).

## Research Agent → Produção (pipeline completo)

```text
RESEARCH AGENT (LLM: gera hipótese)
      ↓
HYPOTHESIS (registada em learned_rules/research_hypotheses, status=candidate)
      ↓
BACKTEST (DET)
      ↓
OUT-OF-SAMPLE (DET)
      ↓
PAPER TRADING (mínimo: 30–90 dias corridos, N trades mínimo por config)
      ↓
RISK REVIEW (DET + admin)
      ↓
APPROVAL → strategies.lifecycle_stage = 'small_capital' → 'production'
```

O Research Agent nunca escreve `lifecycle_stage`. Só propõe.

## Critério de promoção mínimo (Fase 6+, configurável)

```yaml
promotion:
  min_paper_trades: 30
  min_paper_days: 30
  max_drawdown_pct: 10
  min_expectancy: 0            # tem de ser positiva
  min_sharpe_like: 0.5
  degradation_tolerance_pct: 20  # desvio máximo vs. backtest antes de reverter a WARNING
```
