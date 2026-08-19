# 01 — Estrutura do Repositório

Monorepo. Um único checkout contém backend, frontend, motores quant e o worker 24/7.

> Esta secção descrevia originalmente a estrutura planeada antes de qualquer código
> existir. Depois de 7 fases implementadas, a árvore real divergiu do plano em vários
> pontos bem justificados (ver `12-roadmap.md` para o porquê de cada fase) — o que se
> segue é a estrutura real, não a aspiracional.

```text
ogrownt/
├── apps/
│   ├── api/                       # FastAPI — camada HTTP fina sobre os packages
│   │   ├── main.py                # monta todos os routers + CORSMiddleware
│   │   ├── deps.py                # get_session, get_current_admin (JWT Bearer)
│   │   ├── security.py            # hash/verify password, create/decode JWT
│   │   ├── schemas.py             # todos os Pydantic response/request models
│   │   └── routers/
│   │       ├── auth.py            # login/logout/me
│   │       ├── system.py          # health (público), status, kill switch, risk-limits
│   │       ├── assets.py
│   │       ├── market_data.py
│   │       ├── portfolio.py
│   │       ├── strategies.py      # lista, performance, promotion-check/promote/restore
│   │       ├── opportunities.py   # signals, opportunities, regime
│   │       ├── risk.py
│   │       ├── trading.py         # positions, orders, trades, trades/{id}/why
│   │       ├── news.py
│   │       ├── patterns.py
│   │       ├── learning.py        # strategy-performance, trade-journal, memory
│   │       ├── research.py        # learned_rules
│   │       ├── backtests.py       # backtests, walkforward, optimize (Fase 6/7)
│   │       ├── alerts.py
│   │       └── analytics.py       # overview agregado (Fase 7)
│   │
│   ├── worker/                    # processo 24/7, um loop, sem framework de agentes
│   │   ├── main.py                # loop principal — cada cadência com o seu intervalo
│   │   ├── scanner.py             # Market Data Agent (Fase 1)
│   │   ├── history.py             # backfill de histórico para novos ativos
│   │   ├── strategy_runner.py     # regime + padrões + estratégias + scoring (Fase 2/4)
│   │   ├── risk_execution.py      # Risk Engine + paper execution inline (Fase 3)
│   │   ├── trade_monitor.py       # fecha posições + Learning Agent por trade (Fase 3/5)
│   │   ├── news_agent.py          # ingestão + interpretação LLM (Fase 4)
│   │   └── alerts.py              # ciclo de entrega de alertas (Fase 7)
│   │
│   └── dashboard/                 # Next.js (App Router) — único frontend, single user
│       ├── app/
│       │   ├── dashboard/page.tsx # ecrã único — todos os painéis (Server Component)
│       │   ├── login/page.tsx
│       │   ├── page.tsx           # redirect para /login ou /dashboard
│       │   └── api/{login,logout}/route.ts  # cookie httpOnly, nunca exposto ao JS cliente
│       ├── components/            # badges (Risk/Regime/Tier/Lifecycle), StatCard, EquitySparkline
│       ├── lib/api.ts             # fetch client — todas as rotas exceto health exigem token
│       └── proxy.ts                # redireciona /dashboard sem cookie para /login
│
├── packages/
│   ├── data/connectors/
│   │   ├── market/                # MarketDataProvider Protocol + MockMarketDataProvider
│   │   └── news/                  # NewsProvider Protocol + MockNewsProvider
│   │
│   ├── quant/                     # núcleo determinístico
│   │   ├── indicators/            # SMA/EMA/RSI/ATR/ROC/volatilidade/trend strength
│   │   ├── regime/                # classificador baseado em regras (+ panic/euphoria via news)
│   │   ├── patterns/               # 8 detetores técnicos/estatísticos/cross-asset + performance tracking
│   │   ├── strategies/            # Trend Following, Momentum, Breakout, Mean Reversion
│   │   ├── scoring/                # Opportunity Scoring Engine (07-scoring-engine.md)
│   │   └── learning/               # strategy_stats, quarantine, research (DET), memory, degradation, promotion
│   │
│   ├── risk/                       # Risk Engine + Safety Belts (08-risk-engine.md)
│   │   ├── position_sizing.py
│   │   ├── correlation_guard.py
│   │   ├── safety_belt.py
│   │   ├── monitor.py              # transições de safety belt -> Alert
│   │   ├── engine.py                # pipeline de decisão de 10 passos
│   │   └── config.py
│   │
│   ├── execution/                  # Execution Engine — só paper, nenhum adapter real existe
│   │   ├── adapters/
│   │   │   ├── base.py             # ExecutionProvider Protocol
│   │   │   └── paper.py            # único provider implementado
│   │   ├── fills.py                 # simulação de spread/slippage/fees, partilhada com o backtest
│   │   └── order_manager.py         # único código que cria Position/Order/Trade
│   │
│   ├── backtest/                    # Fase 6 — motor de backtest orientado a eventos
│   │   ├── engine.py                 # sem look-ahead, reutiliza o pipeline do worker
│   │   ├── portfolio.py              # SimulatedPortfolio isolado (nunca toca tabelas reais)
│   │   ├── risk.py                   # reutiliza as funções puras do Risk Engine
│   │   ├── walkforward.py            # janelas consecutivas + veredicto de consistência
│   │   ├── stability.py              # perturbação de parâmetros ±20%
│   │   └── optimize.py               # Fase 7 — grid search limitado, nunca aplica
│   │
│   ├── notifications/                # Fase 7 — entrega de alertas
│   │   ├── channels/                 # NotificationChannel Protocol: email, telegram, whatsapp (stub honesto)
│   │   └── dispatcher.py             # fan-out para todos os canais, nunca decide
│   │
│   ├── analytics/                    # Fase 7 — agregação pura de leitura
│   │   └── overview.py
│   │
│   ├── portfolio/                    # Portfolio Engine
│   │   └── state.py                  # equity/cash/exposure/drawdown, portfolio_snapshots
│   │
│   ├── llm/                          # única camada que fala com a Anthropic API
│   │   ├── client.py                 # degrada honestamente sem ANTHROPIC_API_KEY
│   │   ├── news_intelligence.py      # interpretação de notícias (Fase 4)
│   │   ├── learning.py                # hipótese de trade journal (Fase 5)
│   │   ├── research.py                # propõe learned_rules candidatas (Fase 5)
│   │   └── prompts/
│   │
│   └── shared/                       # usado por todos os outros packages
│       ├── models.py                  # todos os modelos SQLAlchemy 2.0
│       ├── settings.py                # Pydantic Settings — recusa arrancar com segredos por omissão
│       ├── db.py
│       ├── logging.py
│       └── market_data.py             # get_latest_close, partilhado por API/worker/backtest
│
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml      # postgres + migrate + api + worker + dashboard (sem redis)
│   │   ├── Dockerfile.api            # também usado, sem alterações, pelo serviço `migrate`
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.dashboard      # todas as três correm como utilizador não-root
│   └── migrations/                   # Alembic — uma migração por fase, 0001 a 0007
│
├── scripts/
│   └── seed.py                       # admin, universo de ativos, portfolio inicial, estratégias (idempotente)
│
├── tests/                            # pytest, plano (sem unit/integration/backtest_fixtures
│                                      # separados) — isolamento real via savepoint+rollback
│                                      # por teste (tests/conftest.py)
│
├── docs/blueprint/                    # esta Blueprint 2.0
│
├── .github/workflows/ci.yml           # ruff + mypy + pytest + eslint/build + docker build
├── pyproject.toml                     # dependencies, [tool.ruff], [tool.mypy]
├── .env.example
└── README.md
```

## O que não existe (e porquê)

- **`packages/memory/` como package separado** — a Market Memory acabou em
  `packages/quant/learning/memory.py`, junto do resto do Learning Engine que a
  escreve/lê, em vez de um package independente sem outros consumidores.
- **`apps/worker/orchestrator.py` / `apps/worker/agents/`** — não há um "Master Agent"
  a despachar sub-agentes; `apps/worker/main.py` é um único loop com uma cadência por
  responsabilidade (cada uma com o seu próprio intervalo configurável), mais simples de
  raciocinar sobre e testar do que uma camada de orquestração extra sem necessidade real.
- **WebSocket (`/ws/live`)** — nunca implementado. O dashboard é Server Components +
  fetch, sem necessidade de push em tempo real para um utilizador único a olhar para um
  ecrã de cada vez.
- **`packages/execution/adapters/{alpaca,binance,ibkr}.py`** — live trading está fora de
  âmbito até validação estatística completa (`12-roadmap.md §Evolução futura`); só existe
  `PaperExecutionProvider`.
- **redis** — nada neste sistema precisa de pub/sub ou cache distribuída para um único
  utilizador; removido do `docker-compose.yml` planeado.

## Regras de dependência entre packages

```text
apps/api      → packages/shared, packages/quant (leitura), packages/risk (leitura), packages/analytics, packages/backtest
apps/worker   → todos os packages exceto packages/backtest e packages/analytics
apps/backtest_worker → packages/backtest, packages/shared, packages/quant, packages/risk (leitura) — nunca packages/execution além do fill simulator
packages/backtest → packages/quant, packages/risk, packages/execution, packages/portfolio (nunca escreve nas tabelas de paper trading)
packages/quant    → packages/shared, packages/data
packages/risk     → packages/shared
packages/execution → packages/shared, packages/risk (consulta, nunca decide)
packages/notifications → packages/shared (lê Alert, nunca decide o que é alerta-digno)
packages/llm      → packages/shared  (NUNCA importa packages/execution)
```

A regra mais importante: **`packages/llm` nunca deve conseguir chamar
`packages/execution` diretamente.** Isso é o que torna a regra "LLM ≠ Trading Engine"
estrutural (não apenas uma convenção de prompt) — ver `04-agents-architecture.md §Guardrail
Estrutural`.

**"PROMPT 7" acrescenta `apps/backtest_worker`** — um processo *separado* de
`apps/worker`, não uma cadência dentro dele: `apps/worker → ... exceto
packages/backtest` já existia antes desta fase por um motivo real (isolar o
loop de trading ao vivo de compute pesado sob demanda), e adicionar
walk-forward optimization/Monte Carlo/stress test como uma cadência teria
violado exatamente essa regra. Ver `apps/backtest_worker/main.py`.
