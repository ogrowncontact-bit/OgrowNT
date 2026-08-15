# 04 — Arquitetura dos Agentes

## Guardrail estrutural: `LLM ≠ Trading Engine`

Cada agente abaixo é anotado com o seu **modo de decisão**:

- **DET** (determinístico/estatístico) — código Python puro, sem LLM. Produz números
  auditáveis e reprodutíveis (mesma entrada → mesma saída).
- **LLM** — usa um modelo de linguagem. Produz texto/estruturas interpretativas
  (rationale, hipóteses, resumos). **Nunca** escreve diretamente em `positions`,
  `orders` ou nos limites de `system_state`/risk config.

Estruturalmente (ver `01-repo-structure.md`), `packages/llm` não importa
`packages/execution`. Qualquer output de um agente LLM que possa influenciar uma
decisão de trade passa sempre por um agente DET antes de chegar ao Execution Engine.

## Agent 01 — Master Supervisor (`orchestrator.py`) — DET (orquestração)

Coordena o ciclo (`05-event-flow.md`), invoca os restantes agentes pela ordem do
Decision Pipeline, e é o único a poder transicionar `system_state.safety_belt_level`
(a pedido do Risk Agent — nunca por iniciativa própria de um LLM). Regista toda
transição em `audit_log`.

## Agent 02 — Market Data Agent / Scanner — DET

- Faz polling dos conectores em `packages/data/connectors/market/*` por timeframe.
- Corre **data quality checks** antes de persistir (`08-risk-engine.md §Data
  Quality`): timestamp válido, sem gaps anómalos, sem duplicados, fonte "up".
- Se falhar: grava `data_quality='DATA_UNAVAILABLE'` — nunca interpola/inventa um
  valor. Nunca reporta um valor sintético como se fosse real.
- Saída (evento `MARKET_DATA_UPDATED`):
```json
{"asset": "BTC/USDT", "timeframe": "5m", "ts": "...", "ohlcv": {...}, "data_quality": "high"}
```

## Agent 03 — News Intelligence Agent — LLM (interpretação) sobre dados DET

- Ingestão de notícias (DET, `packages/data/connectors/news`) — nunca gera notícia,
  só lê fontes reais configuradas.
- Interpretação (LLM): para cada notícia relevante, produz `EVENT → ASSET →
  DIRECTION → IMPACT → CONFIDENCE → TIME_HORIZON` com `rationale`, gravado em
  `news_impact`. Prompt em `11-prompts/news-intelligence-agent.md`.
- Proibido inventar notícia/evento inexistente — se a fonte não devolveu nada,
  não há linha em `news_events` para aquele período (não um placeholder).

## Agent 04 — Technical Analyst — DET

Calcula indicadores (`packages/quant/indicators`) por ativo/timeframe: tendência,
momentum, volume, volatilidade, suporte/resistência. Biblioteca extensível — novos
indicadores são plugins que implementam `Indicator.compute(ohlcv) -> Series`.

## Agent 05 — Pattern Engine — DET

Classifica `TREND | BREAKOUT | REVERSAL | MOMENTUM | MEAN_REVERSION | VOLATILITY |
ANOMALY | CROSS_ASSET` (`packages/quant/patterns`). Cada deteção grava uma linha em
`patterns` e atualiza `pattern_performance` quando o trade associado fecha.

## Agent 06 — Market Regime Engine — DET

Classifica `TRENDING_BULL | TRENDING_BEAR | RANGING | HIGH_VOLATILITY |
LOW_VOLATILITY | PANIC | EUPHORIA | TRANSITION | UNKNOWN`, por ativo e globalmente
(`packages/quant/regime`), a partir de volatilidade realizada, ADX-like trend
strength, e correlação cross-asset. Grava em `market_regimes`.

## Agent 07 — Strategy Engine — DET (interface plugável)

Cada estratégia implementa:

```python
class Strategy(Protocol):
    name: str
    version: str
    def analyze(self, market_data: MarketContext) -> AnalysisResult: ...
    def generate_signal(self, market_data: MarketContext) -> Signal | None: ...
    def calculate_expected_value(self, context: AnalysisResult) -> float: ...
    def evaluate_performance(self) -> StrategyPerformance: ...
```

Estratégias iniciais (Fase 2): `TrendFollowing`, `Momentum`, `Breakout`,
`MeanReversion`. Cada uma sabe o seu `best_regime`/`worst_regime` esperado
(hipótese inicial), validado depois pelo Learning Engine.

## Agent 08 — Opportunity Scoring Engine — DET

Ver `07-scoring-engine.md`. Pesos centralizados e configuráveis (não hardcoded).

## Agent 09 — Risk Engine — DET, com poder de veto

Ver `08-risk-engine.md`. É o único agente cuja resposta pode **bloquear** um sinal
independentemente do score. Nenhum outro agente (incluindo o Master Supervisor) pode
ignorar um `risk_decisions.approved = false`.

## Agent 10 — Portfolio Engine — DET

Mantém a visão agregada: cash, posições, exposição, correlação, `Portfolio Risk`
(nunca analisa um trade isoladamente — sempre no contexto do portfolio). Corre o
Correlation Guard antes de qualquer aprovação do Risk Engine.

## Agent 11 — Execution Engine — DET

Só conhece `ExecutionProvider` (`03-api-spec.md`). No MVP, apenas
`PaperExecutionProvider` está habilitado. Simula fees, spread, slippage, partial
fills.

## Agent 12 — Trade Monitor — DET

Após abertura: acompanha preço/stop/target/P&L/volatilidade/regime/notícias, e
reavalia periodicamente `A tese original ainda é válida?` (regra determinística por
estratégia, ex.: regime mudou de `TRENDING_BULL` para `RANGING` → invalida tese de
`TrendFollowing`).

## Agent 13 — Learning Agent — LLM (hipótese) + DET (estatística)

- DET: recalcula `strategy_performance`, `pattern_performance`,
  `strategy health score` a cada trade fechado.
- LLM: para trades com `expected_outcome ≠ actual_outcome`, gera hipótese de causa
  (`trade_journal.hypothesis`) — nunca aplica a hipótese automaticamente; cria uma
  `LEARNING PROPOSAL` (`learned_rules` com `status='candidate'`) que só é aplicada
  (`status='validated'`) após validação estatística (sample size mínimo,
  significância) feita em DET.

## Agent 14 — Research Agent — LLM (geração de hipóteses) + DET (validação)

Não pode colocar estratégias em produção. Segue sempre
`IDEA → HYPOTHESIS → BACKTEST → OUT-OF-SAMPLE → PAPER TEST → RISK REVIEW → APPROVAL`
(`10-backtesting-paper-trading.md`). Só o Risk Engine + admin aprovam a transição
para `production`.

## Resumo: quem pode escrever onde

| Tabela | Quem escreve |
|---|---|
| `positions`, `orders`, `trades` | apenas Execution Engine (DET), após `risk_decisions.approved=true` |
| `risk_decisions`, `system_state` | apenas Risk Engine (DET) / admin via API |
| `strategies.lifecycle_stage` | Research Agent propõe, Risk Engine + admin aprovam |
| `news_impact`, `trade_journal.hypothesis`, `learned_rules(candidate)` | agentes LLM |
| `learned_rules(validated)` | apenas processo DET de validação estatística |
