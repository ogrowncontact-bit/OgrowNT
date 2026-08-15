# 03 — API Spec (REST + WebSocket)

Backend: FastAPI. Autenticação: JWT (utilizador único — admin). Todas as rotas abaixo,
exceto `/api/auth/login` e `/api/system/health`, exigem `Authorization: Bearer <token>`.

## Auth

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/auth/login` | `{email, password}` → `{access_token, expires_at}` |
| POST | `/api/auth/logout` | invalida a sessão corrente |
| GET  | `/api/auth/me` | dados do admin autenticado |

## System

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/system/health` | público. Estado de cada componente (`market_data`, `news`, `database`, `ai_services`, `risk_engine`, `execution`, `learning_engine`) → `🟢/🟡/🔴` + `DEGRADED_MODE` se algum crítico falhar |
| GET | `/api/system/status` | `safety_belt_level`, `trading_enabled`, uptime, última iteração do loop |
| POST | `/api/system/kill-switch` | ativa o Kill Switch manualmente (admin) |
| POST | `/api/system/kill-switch/release` | desativa, só após checklist de diagnóstico (`08-risk-engine.md`) |
| PATCH | `/api/system/risk-limits` | atualiza limites configuráveis (ver `08-risk-engine.md §Config`) |

## Assets & Market Data

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/assets` | lista o universo configurado (`?asset_class=`, `?is_active=`) |
| POST | `/api/assets` | adiciona ativo ao universo (admin) |
| PATCH | `/api/assets/{id}` | ativa/desativa |
| GET | `/api/market-data/{asset_id}` | `?timeframe=&from=&to=` → OHLCV |
| GET | `/api/market-data/{asset_id}/latest` | último preço + `data_quality` |

## News & Regime

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/news` | eventos recentes + `news_impact` associado |
| GET | `/api/regime` | `?asset_id=` regime atual por ativo (e global) |

## Strategies & Signals

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/strategies` | lista + `lifecycle_stage` |
| GET | `/api/strategies/{id}/performance` | métricas (`02-database-schema.md §strategy_performance`) |
| GET | `/api/signals` | sinais recentes gerados pelo Strategy Engine |
| GET | `/api/opportunities` | sinais + score, ordenados por `final_score` (o que o dashboard consome) |
| GET | `/api/opportunities/{signal_id}` | detalhe completo — usado no ecrã "Why?" |

## Risk & Portfolio

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/risk` | estado do Risk Engine, safety belt, limites atuais, últimas rejeições |
| GET | `/api/portfolio` | equity, cash, exposure, P&L dia/semana/mês, drawdown |
| GET | `/api/portfolio/history` | série temporal de `portfolio_snapshots` |
| GET | `/api/positions` | posições abertas |
| GET | `/api/positions/{id}` | detalhe + thesis (`entry_thesis`, `exit_reason` quando fechado) |
| GET | `/api/orders` | histórico de ordens (paper) |
| GET | `/api/trades` | trades fechados |
| GET | `/api/trades/{id}/why` | breakdown do score + risk checks que levaram à decisão |

## Learning & Research

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/learning` | resumo: padrões descobertos, estratégias em melhoria/deterioração |
| GET | `/api/learning/journal` | `trade_journal` paginado |
| GET | `/api/research/hypotheses` | hipóteses em pipeline (`idea → ... → approval`) |
| GET | `/api/research/experiments/{id}` | resultado de backtest/OOS de uma hipótese |

## Alerts

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/alerts` | `?severity=&acknowledged=` |
| POST | `/api/alerts/{id}/ack` | marca como visto |

## WebSocket

| Canal | Payload | Frequência |
|---|---|---|
| `/ws/live` | `{type: 'portfolio'\|'position'\|'opportunity'\|'alert'\|'system_state', data}` | push em cada evento relevante do event bus (`05-event-flow.md`) |

## Execution Adapter (interface interna, não é API HTTP pública)

Usada por `packages/execution`, comum a paper e (futuramente) live:

```python
class ExecutionProvider(Protocol):
    def submit_order(self, order: OrderRequest) -> OrderResult: ...
    def cancel_order(self, broker_order_id: str) -> None: ...
    def get_order(self, broker_order_id: str) -> OrderStatus: ...
    def get_positions(self) -> list[PositionSnapshot]: ...
    def get_balance(self) -> BalanceSnapshot: ...
```

Implementações: `PaperExecutionProvider` (Fase 3, único habilitado no MVP). Adapters reais
(`AlpacaProvider`, `BinanceProvider`, `IBKRProvider`) ficam com `enabled=False` por
configuração até validação explícita — nunca instanciados por omissão.
