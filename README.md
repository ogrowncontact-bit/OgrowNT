# OgrowNT

**Private AI quant research & paper trading system.** Single-user, 24/7, currently
**paper trading only** — no real orders are ever sent. See the full engineering
specification in [`docs/blueprint/`](docs/blueprint/00-overview.md).

## Status: Phase 3 (Risk & Execution)

Per [`docs/blueprint/12-roadmap.md`](docs/blueprint/12-roadmap.md):

- **Phase 1 (Brain):** project, database, authentication, dashboard, a market-data
  abstraction (mock provider for now), the paper portfolio, a basic scanner, logging.
- **Phase 2 (Intelligence):** technical indicators, a rule-based Regime Engine
  (5 of 9 regimes — the rest need Phase 4's News Intelligence Agent), 4 pluggable
  strategies (Trend Following, Momentum, Breakout, Mean Reversion), and a
  deterministic Opportunity Scoring Engine.
- **Phase 3 (Risk & Execution):** Portfolio Engine, Risk Engine (position sizing,
  real Pearson correlation guard, Safety Belts, a 10-step decision pipeline with
  veto power), a `PaperExecutionProvider` (simulated spread/slippage/fees), and a
  Trade Monitor that closes positions on stop/target hits or an invalidated
  thesis. The worker now runs the full `SIGNAL → RISK → PAPER ORDER → POSITION →
  MONITOR → CLOSE` loop on its own — verified live, not just in tests.

News/patterns and learning arrive in later phases — **every order is `is_paper =
true`; no broker/exchange adapter is registered; nothing in this repo can send a
live order or read a real broker/exchange key.**

## Architecture at a glance

```text
apps/
  api/         FastAPI backend (auth, system health, assets, market data, portfolio,
               strategies, opportunities/signals, regime, risk, positions/orders/trades)
  worker/      24/7 loop: Market Data Agent (scan), Trade Monitor + safety-belt
               refresh (every scan), Strategy Engine cycle (history backfill,
               regime, strategies, scoring, Risk Engine, paper execution)
  dashboard/   Next.js dashboard (single admin user)
packages/
  shared/      DB models, settings, logging, OHLCV lookup — shared across apps/packages
  data/        Market data provider interface + mock provider (incl. historical backfill)
  quant/       indicators, regime classifier, pluggable strategies, scoring engine
  portfolio/   equity/cash/exposure/drawdown computation, append-only snapshot ledger
  risk/        position sizing, correlation guard, safety belts, the veto-power decision pipeline
  execution/   ExecutionProvider interface, PaperExecutionProvider, order manager
infra/
  docker/      docker-compose + Dockerfiles
  migrations/  Alembic
scripts/       seed.py — admin user, asset universe, paper portfolio, strategy registry
config/        risk_limits.yaml, scoring_weights.yaml — both live-editable (risk
               limits via PATCH /api/system/risk-limits)
docs/blueprint/  full technical spec (architecture, DB schema, API, agents,
                 event flow, memory, scoring, risk engine, dashboard spec,
                 backtesting, LLM prompts, roadmap)
```

## Running it

### With Docker (recommended)

```bash
cp .env.example .env   # edit ADMIN_EMAIL / ADMIN_PASSWORD / JWT_SECRET
docker compose -f infra/docker/docker-compose.yml up --build
```

- API: http://localhost:8000 (docs at `/docs`)
- Dashboard: http://localhost:3000 (redirects to `/login`)

The `migrate` service applies Alembic migrations and runs `scripts/seed.py`
(creates the admin user, seeds ~20 assets across crypto/forex/equities/indices/
commodities, the initial €10,000 paper portfolio, and registers the 4 Phase 2
strategies) before `api`/`worker` start. The worker backfills enough mock history
per asset on startup so opportunities show up within the first strategy cycle
rather than after `MIN_CANDLES_REQUIRED` real minutes.

### Locally, without Docker

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # point DATABASE_URL at a local Postgres 16
alembic upgrade head
python -m scripts.seed
uvicorn apps.api.main:app --reload &
python -m apps.worker.main &

# Tests
pytest

# Dashboard
cd apps/dashboard && npm install && npm run dev
```

## Design principles (non-negotiable — see `docs/blueprint/00-overview.md`)

- `LLM ≠ Trading Engine` — language models research, interpret and explain; sizing,
  risk and execution are always deterministic code.
- Capital preservation > opportunity. No forced trading: when there's no clear edge,
  `NO TRADE` is the correct answer.
- Never chase losses — no code path increases risk in response to a recent loss.
- The Risk Engine has veto power over every trade; nothing overrides it.
- No hallucinated market data — a missing value is reported as `DATA_UNAVAILABLE`,
  never invented.
- Every decision is explainable and auditable.

## Docs

Start at [`docs/blueprint/00-overview.md`](docs/blueprint/00-overview.md) for the
full architecture, then follow the numbered documents (`01`–`12`) for the database
schema, API, agents, event flow, memory system, scoring engine, risk engine,
dashboard spec, backtesting/paper trading, LLM prompts, and the phased roadmap.
