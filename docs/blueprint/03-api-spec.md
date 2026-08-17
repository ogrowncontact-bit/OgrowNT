# 03 — API Spec (REST)

Backend: FastAPI. Autenticação: JWT (utilizador único — admin). Todas as rotas abaixo,
exceto `/api/auth/login` e `/api/system/health`, exigem `Authorization: Bearer <token>`
(`Depends(get_current_admin)` em `apps/api/deps.py`) — incluindo todos os `GET`, não só
as ações que escrevem. Não existe WebSocket implementado (o dashboard usa Server
Components + fetch, sem push em tempo real) — a secção WebSocket do rascunho original
desta spec nunca foi construída e foi removida daqui.

## Auth (`apps/api/routers/auth.py`)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/api/auth/login` | pública | `{email, password}` → `{access_token, expires_at}` |
| POST | `/api/auth/logout` | admin | JWT stateless — nada a invalidar no servidor, o cliente descarta o token |
| GET  | `/api/auth/me` | admin | dados do admin autenticado |

## System (`apps/api/routers/system.py`)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/system/health` | pública | estado de cada componente (`database`, `market_data`, `risk_engine`, `news_feed`, `ai_services`) → `green/yellow/red` por componente + `overall` |
| GET | `/api/system/status` | admin | `safety_belt_level`, `trading_enabled`, `updated_at`, `updated_reason` |
| POST | `/api/system/kill-switch` | admin | ativa o Kill Switch manualmente — escreve `AuditLog` + `Alert` critical |
| POST | `/api/system/kill-switch/release` | admin | desativa manualmente — escreve `AuditLog` + `Alert` info |
| PATCH | `/api/system/risk-limits` | admin | merge parcial em `config/risk_limits.yaml` (fonte de verdade fica no YAML, não duplicada em DB) |

## Assets & Market Data

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/assets` | admin | `?asset_class=&is_active=` |
| POST | `/api/assets` | admin | adiciona ativo ao universo |
| PATCH | `/api/assets/{id}` | admin | ativa/desativa |
| GET | `/api/market-data/{asset_id}` | admin | `?timeframe=&since=&limit=` → OHLCV |
| GET | `/api/market-data/{asset_id}/latest` | admin | última candle + `data_quality` |

## News & Patterns & Regime

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/news` | admin | `?limit=` eventos recentes + `news_impact` associado por ativo |
| GET | `/api/patterns` | admin | `?asset_id=&limit=` deteções recentes |
| GET | `/api/patterns/performance` | admin | win-rate/expectancy por `pattern_type`+`regime` |
| GET | `/api/regime` | admin | `?asset_id=` último regime conhecido por ativo |

## Strategies & Signals & Opportunities

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/strategies` | admin | lista + `lifecycle_stage` |
| GET | `/api/strategies/{id}/performance` | admin | resumo leve (ver também `/api/learning/strategy-performance` para o breakdown completo) |
| GET | `/api/strategies/{id}/promotion-check` | admin | DET puro: elegibilidade + razões, nunca aplica nada |
| POST | `/api/strategies/{id}/promote` | admin | revalida server-side e avança `lifecycle_stage` (`paper→small_capital→production`) |
| POST | `/api/strategies/{id}/restore` | admin | tira uma estratégia da quarantine |
| GET | `/api/signals` | admin | todos os sinais, incluindo tier `ignore` (auditoria) |
| GET | `/api/opportunities` | admin | `?limit=` sinais com score, exclui tier `ignore`, ordenado por `final_score` |
| GET | `/api/opportunities/{signal_id}` | admin | breakdown completo do score — usado no ecrã "Why?" |

## Risk & Portfolio & Trading

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/risk` | admin | `?limit=` estado do Risk Engine + últimas `risk_decisions` |
| GET | `/api/portfolio` | admin | equity, cash, exposure, P&L, drawdown (último snapshot) |
| GET | `/api/portfolio/history` | admin | `?limit=` série de `portfolio_snapshots` |
| GET | `/api/positions` | admin | `?status_filter=open\|closed` |
| GET | `/api/orders` | admin | `?limit=` histórico de ordens (paper) |
| GET | `/api/trades` | admin | `?limit=` trades fechados |
| GET | `/api/trades/{id}/why` | admin | trade + posição + score + risk decision/checks completos |

## Backtesting (`apps/api/routers/backtests.py`)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/api/backtests` | admin | corre um backtest orientado a eventos, persiste em `backtest_runs` |
| GET | `/api/backtests` | admin | `?strategy_id=&limit=` lista resumida (sem equity_curve/trades) |
| GET | `/api/backtests/{id}` | admin | detalhe completo, incluindo equity_curve e trades |
| POST | `/api/backtests/walkforward` | admin | janelas de teste consecutivas + veredicto de consistência |
| POST | `/api/backtests/optimize` | admin | grid search limitado sobre os parâmetros da estratégia, ranqueado por expectancy pooled — nunca escreve nos parâmetros por omissão |

## Learning & Research

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/learning/strategy-performance` | admin | health score + métricas completas por estratégia |
| GET | `/api/learning/trade-journal` | admin | `?limit=` expected vs actual + hipótese LLM quando divergem |
| GET | `/api/learning/memory` | admin | `?limit=` contexto+outcome por sinal |
| GET | `/api/learning/memory/similar` | admin | `?regime=&pattern_type=&direction=&k=` correspondência estruturada |
| GET | `/api/research/rules` | admin | `?status=&limit=` `learned_rules` candidatas/validadas/rejeitadas |

## Alerts (`apps/api/routers/alerts.py`)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/alerts` | admin | `?severity=&acknowledged=&limit=` |
| POST | `/api/alerts/{id}/ack` | admin | marca como reconhecido |

## Advanced Analytics (`apps/api/routers/analytics.py`)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/analytics/overview` | admin | equity curve, trade stats, drawdown, distribuição de tiers/regimes, leaderboard de padrões — agregação pura de leitura, nada novo escrito |

## Execution Adapter (interface interna, não é API HTTP pública)

Usada por `packages/execution`, comum a paper e (futuramente) live:

```python
class ExecutionProvider(Protocol):
    def submit_order(self, order: OrderRequest) -> OrderResult: ...
```

Implementação: `PaperExecutionProvider` (Fase 3, único que existe). Nenhum adapter
real (`AlpacaProvider`, `BinanceProvider`, `IBKRProvider`, ...) foi criado — live
trading está fora de âmbito até validação estatística completa (`12-roadmap.md
§Evolução futura`), não apenas desligado por configuração.
