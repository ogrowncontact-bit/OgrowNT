# 01 — Estrutura do Repositório

Monorepo. Um único checkout contém backend, frontend, motores quant e definições dos
agentes.

```text
ogrownt/
├── apps/
│   ├── api/                     # FastAPI — HTTP + WebSocket, camada fina sobre os packages
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── portfolio.py
│   │   │   ├── opportunities.py
│   │   │   ├── trades.py
│   │   │   ├── learning.py
│   │   │   ├── system.py        # status, safety belt, kill switch
│   │   │   └── ws.py            # WebSocket live feed
│   │   ├── deps.py
│   │   └── settings.py
│   │
│   ├── worker/                  # processo 24/7: orquestrador + todos os agentes
│   │   ├── main.py              # entrypoint do loop (05-event-flow.md)
│   │   ├── orchestrator.py      # Master Agent
│   │   └── agents/
│   │       ├── market_data_agent.py
│   │       ├── news_agent.py
│   │       ├── pattern_agent.py
│   │       ├── regime_agent.py
│   │       ├── strategy_agent.py
│   │       ├── scoring_agent.py
│   │       ├── risk_agent.py
│   │       ├── portfolio_agent.py
│   │       ├── execution_agent.py
│   │       ├── monitor_agent.py
│   │       ├── learning_agent.py
│   │       └── research_agent.py
│   │
│   └── dashboard/                # Next.js — único frontend (single user)
│       ├── app/
│       │   ├── page.tsx          # Home
│       │   ├── positions/
│       │   ├── opportunities/
│       │   ├── trades/[id]/why/  # aba "Why?"
│       │   ├── learning/
│       │   ├── brain/
│       │   └── alerts/
│       ├── components/
│       └── lib/api-client.ts
│
├── packages/
│   ├── data/                     # conectores de mercado, news, macro
│   │   ├── connectors/
│   │   │   ├── market/           # preço/volume (crypto, forex, equities, índices, commodities)
│   │   │   ├── news/
│   │   │   └── macro/
│   │   └── normalizers/
│   │
│   ├── quant/                    # núcleo determinístico/estatístico
│   │   ├── indicators/
│   │   ├── patterns/             # técnicos, estatísticos, cross-market
│   │   ├── regime/
│   │   ├── strategies/
│   │   │   ├── momentum.py
│   │   │   ├── trend_following.py
│   │   │   ├── mean_reversion.py
│   │   │   ├── breakout.py
│   │   │   ├── stat_arb.py
│   │   │   ├── news_momentum.py
│   │   │   ├── volatility.py
│   │   │   └── cross_asset.py
│   │   ├── scoring/               # Opportunity Scoring Engine (07)
│   │   └── backtest/              # motor de backtest + walk-forward (10)
│   │
│   ├── risk/                      # Risk Engine + Portfolio Engine + Safety Belts (08)
│   │   ├── position_sizing.py
│   │   ├── correlation_guard.py
│   │   ├── drawdown_control.py
│   │   ├── safety_belt.py
│   │   └── kill_switch.py
│   │
│   ├── execution/                 # Execution Engine + adapters de broker/exchange
│   │   ├── adapters/
│   │   │   ├── base.py            # interface comum (03-api-spec.md)
│   │   │   ├── paper.py           # simulador (custos, slippage, spread)
│   │   │   ├── alpaca.py
│   │   │   ├── binance.py
│   │   │   └── ibkr.py
│   │   └── order_manager.py
│   │
│   ├── memory/                    # Market Memory, Strategy Memory, Pattern Memory (06)
│   │   ├── embeddings.py
│   │   └── retrieval.py
│   │
│   ├── llm/                       # camada de acesso a LLM (research/interpretação/explicação)
│   │   ├── client.py
│   │   ├── prompts/               # espelha docs/blueprint/11-prompts em runtime
│   │   └── guardrails.py          # aplica a regra "LLM ≠ Trading Engine"
│   │
│   └── shared/                    # tipos partilhados (Pydantic) usados por api/worker/quant
│       ├── models.py               # Asset, Signal, Score, Order, Trade, ...
│       └── events.py                # schemas de eventos (05-event-flow.md)
│
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml     # postgres + redis + api + worker + dashboard
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.dashboard
│   └── migrations/                # Alembic (02-database-schema.md)
│
├── scripts/
│   ├── seed_assets.py             # popula os 20-50 ativos do MVP
│   ├── backtest_cli.py
│   └── replay_market_memory.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── backtest_fixtures/
│
├── docs/
│   └── blueprint/                 # esta Blueprint 2.0
│
├── pyproject.toml
├── .env.example
└── README.md
```

## Regras de dependência entre packages

```text
apps/api      → packages/shared, packages/quant (leitura), packages/risk (leitura)
apps/worker   → todos os packages
packages/quant   → packages/shared, packages/data
packages/risk    → packages/shared
packages/execution → packages/shared, packages/risk (consulta, nunca decide)
packages/llm     → packages/shared, packages/memory  (NUNCA importa packages/execution)
```

A regra mais importante: **`packages/llm` nunca deve conseguir chamar
`packages/execution` diretamente.** Isso é o que torna a regra "LLM ≠ Trading Engine"
estrutural (não apenas uma convenção de prompt) — ver `04-agents-architecture.md §Guardrail
Estrutural`.
