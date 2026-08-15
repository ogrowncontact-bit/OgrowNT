# OgrowNT

**Private AI quant research & paper trading system.** Single-user, 24/7, currently
**paper trading only** — no real orders are ever sent. See the full engineering
specification in [`docs/blueprint/`](docs/blueprint/00-overview.md).

## Status: Phase 1 (Brain)

Per [`docs/blueprint/12-roadmap.md`](docs/blueprint/12-roadmap.md), Phase 1 delivers
the foundation: project, database, authentication, dashboard, a market-data
abstraction (mock provider for now), the paper portfolio, a basic scanner, and
logging. Strategies, scoring, risk engine, execution, news/regime/patterns and
learning arrive in later phases — nothing in this repo sends a live order or reads a
real broker/exchange key.

## Architecture at a glance

```text
apps/
  api/         FastAPI backend (auth, system health, assets, market data, portfolio)
  worker/      24/7 scanner loop (Market Data Agent — Phase 1 slice)
  dashboard/   Next.js dashboard (single admin user)
packages/
  shared/      DB models, settings, logging — shared by api + worker
  data/        Market data provider interface + mock provider
infra/
  docker/      docker-compose + Dockerfiles
  migrations/  Alembic
scripts/       seed.py — admin user, asset universe, initial paper portfolio
config/        risk_limits.yaml, scoring_weights.yaml (consumed from Phase 2+)
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
commodities, and the initial €10,000 paper portfolio) before `api`/`worker` start.

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
