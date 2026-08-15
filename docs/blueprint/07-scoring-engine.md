# 07 — Opportunity Scoring Engine

Motor **determinístico**. Produz um score 0–100 por sinal, gravado em
`opportunity_scores` (`02-database-schema.md`).

## Componentes e pesos (config, não hardcoded)

```yaml
# config/scoring_weights.yaml
weights:
  technical: 0.15
  pattern: 0.15
  regime: 0.15
  historical_edge: 0.15
  liquidity: 0.10
  news: 0.10
  risk_reward: 0.15
  strategy_performance: 0.05
penalties:
  volatility: { max: 15 }
  correlation: { max: 15 }
  execution_cost: { max: 10 }
  drawdown: { max: 10 }
thresholds:
  ignore: 60
  watch: 70
  possible: 80
  high_quality: 90
  # >= 90 => exceptional
```

Estes pesos são a hipótese inicial, **não valores definitivos** — o Learning Engine
pode propor ajustes (como `learned_rules`), mas qualquer mudança de peso é uma
alteração de configuração explícita e auditada, nunca uma escrita automática.

## Fórmula

```python
def compute_score(inputs: ScoringInputs, cfg: ScoringConfig) -> OpportunityScore:
    base = (
        inputs.technical            * cfg.weights.technical +
        inputs.pattern               * cfg.weights.pattern +
        inputs.regime_fit            * cfg.weights.regime +
        inputs.historical_edge       * cfg.weights.historical_edge +
        inputs.liquidity             * cfg.weights.liquidity +
        inputs.news                  * cfg.weights.news +
        inputs.risk_reward           * cfg.weights.risk_reward +
        inputs.strategy_performance  * cfg.weights.strategy_performance
    )  # cada input já normalizado 0-100

    penalty = (
        inputs.volatility_penalty   * cfg.penalties.volatility.max +
        inputs.correlation_penalty  * cfg.penalties.correlation.max +
        inputs.execution_cost_penalty * cfg.penalties.execution_cost.max +
        inputs.drawdown_penalty     * cfg.penalties.drawdown.max
    )

    final = max(0.0, min(100.0, base - penalty))
    return OpportunityScore(final_score=final, tier=tier_for(final, cfg.thresholds))
```

## Origem de cada input (0–100 normalizado)

| Input | Origem | Nota |
|---|---|---|
| `technical` | Technical Analyst | força/confluência dos indicadores |
| `pattern` | Pattern Engine | força do padrão detetado (`patterns.strength`) |
| `regime_fit` | Regime Engine × Strategy | compatibilidade regime↔estratégia (matriz em `strategy_performance.best_regime/worst_regime`) |
| `historical_edge` | Pattern Memory + Strategy Memory | expectancy histórica em condições semelhantes |
| `liquidity` | Market Data (spread/orderbook) | penaliza spread alto / livro fino |
| `news` | News Intelligence | `news_impact.confidence` × alinhamento de direção |
| `risk_reward` | Signal (entry/stop/target) | `(target-entry)/(entry-stop)` normalizado |
| `strategy_performance` | Strategy Memory | Strategy Health Score recente |
| `volatility_penalty` | Regime Engine | volatilidade excessiva face ao normal do ativo |
| `correlation_penalty` | Portfolio Engine | sobreposição com posições existentes |
| `execution_cost_penalty` | Execution Engine (estimado) | spread + slippage esperado / risco do trade |
| `drawdown_penalty` | Portfolio Engine | reduz score quando o portfolio já está em drawdown (ver Safety Belts) |

## Tiers

| Score | Tier | Ação |
|---|---|---|
| < 60 | `ignore` | descartado, não persiste como oportunidade ativa |
| 60–70 | `watch` | visível no dashboard, não enviado ao Risk Engine |
| 70–80 | `possible` | enviado ao Risk Engine |
| 80–90 | `high_quality` | enviado ao Risk Engine, prioridade de exibição |
| ≥ 90 | `exceptional` | idem, destacado no dashboard |

Score alto **nunca** salta o Risk Engine — é apenas o critério de entrada no pipeline
de risco (`05-event-flow.md §Decision Pipeline`).
