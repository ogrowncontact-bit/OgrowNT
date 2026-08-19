# OgrowNT

**Private AI quant research & paper trading system.** Single-user, 24/7, currently
**paper trading only** — no real orders are ever sent. See the full engineering
specification in [`docs/blueprint/`](docs/blueprint/00-overview.md).

## Status: Phase 7 (Advanced Analytics, Alerts, Optimization) + post-Phase-7 security hardening + Supervisor 24/7 + Market Data Engine + Scanner + Pattern/Strategy/Opportunity confidence & evidence + Risk Engine/Portfolio Intelligence hardening (Risk Center, Risk Heatmap, Strategy Health, configurable Safety Belts) + News Intelligence Center (sentiment, macro calendar, event risk, source consensus)

Per [`docs/blueprint/12-roadmap.md`](docs/blueprint/12-roadmap.md):

- **Phase 1 (Brain):** project, database, authentication, dashboard, a market-data
  abstraction (mock provider for now), the paper portfolio, a basic scanner, logging.
- **Phase 2 (Intelligence):** technical indicators, a rule-based Regime Engine,
  4 pluggable strategies (Trend Following, Momentum, Breakout, Mean Reversion), and
  a deterministic Opportunity Scoring Engine.
- **Phase 3 (Risk & Execution):** Portfolio Engine, Risk Engine (position sizing,
  real Pearson correlation guard, Safety Belts, a multi-step decision pipeline
  with veto power — see "Risk Engine/Portfolio Intelligence hardening" below
  for the Strategy Health/monthly-loss/configurable-belt additions), a
  `PaperExecutionProvider` (simulated spread/slippage/fees), and a
  Trade Monitor that closes positions on stop/target hits or an invalidated
  thesis. The worker runs the full `SIGNAL → RISK → PAPER ORDER → POSITION →
  MONITOR → CLOSE` loop on its own.
- **Phase 4 (News, Regime, Patterns):** a News Intelligence Agent (real LLM
  interpretation via `packages/llm`, degrading honestly — never fabricating — when
  no `ANTHROPIC_API_KEY` is set), a Pattern Engine (8 deterministic detectors:
  trend, breakout, reversal, momentum, mean reversion, volatility, anomaly,
  cross-asset) with its own win-rate tracking, and the full Regime taxonomy
  (`panic`/`euphoria`/`transition` now derived from real news, not guessed). The
  Opportunity Scoring Engine's `pattern` and `news` inputs are real signals now,
  not neutral placeholders.
- **Phase 5 (Learning & Research):** a Learning Agent that recomputes each
  strategy's rolling performance and a deterministic 0-100 Health Score on every
  trade close, and automatically quarantines an underperforming live strategy out
  of new signal generation (restoring one is always a deliberate admin action, never
  automatic). A Trade/Failure Journal records expected-vs-actual outcomes, with an
  LLM hypothesis (never fabricated without a configured LLM) when they diverge. A
  Research Agent proposes candidate `learned_rules` for underperforming
  patterns/strategies, validated — or rejected — only by a separate, independent
  statistical check against freshly-queried trade data, never by the LLM's own
  stated confidence. Market Memory captures the context behind every signal and its
  eventual outcome; without the `pgvector` extension available in this Postgres
  deployment, similarity search is real structured matching rather than fabricated
  embeddings. The Scoring Engine's `historical_edge` and `strategy_performance`
  inputs are real Pattern/Strategy Memory reads now, the last two components that
  were still neutral placeholders.
- **Phase 6 (Backtesting):** an event-driven Backtest Engine that walks real,
  already-persisted OHLCV bars one at a time (no look-ahead — a strategy only ever
  sees candles up to "now"), running the same indicators/regime/pattern/scoring
  pipeline the live worker does, sized and gated by the exact same Risk Engine
  sizing/safety-belt logic against an isolated simulated portfolio that never
  touches the real paper account. Anti-overfitting: walk-forward validation
  (consistency across rolling test windows) and parameter-stability checks
  (perturbing each strategy's numeric parameters ±20% and confirming the verdict
  doesn't flip sign — the 4 strategies now take their parameters as constructor
  arguments for exactly this). A performance-degradation check compares live paper
  performance against a strategy's reference backtest and raises a warning on
  sustained divergence. A config-driven promotion pipeline
  (`config/promotion_criteria.yaml`) gates `paper → small_capital → production`
  transitions on real paper-trading track record — always proposed by DET, always
  applied only through an explicit, server-revalidated admin action, never
  automatically.
- **Phase 7 (Advanced Analytics, Alerts, Optimization):** real alert delivery —
  `EmailChannel` (stdlib `smtplib`) and `TelegramChannel` (Bot API via `httpx`),
  plus an honest `WhatsAppChannel` stub (`is_configured()` always `False` — no
  Business API account available in this environment, documented rather than
  faked). A worker cadence delivers every pending `Alert` through all channels
  and records the per-channel outcome, even when nothing is configured.
  Safety-belt tier changes and manual kill-switch actions now always raise an
  `Alert` (a gap that existed since Phase 3). Parameter optimization
  (`packages/backtest/optimize.py`) runs a bounded grid search over a
  strategy's numeric parameters, judging every candidate by the same
  walk-forward consistency check from Phase 6 — never a single lucky
  backtest — and never writes to a strategy's live defaults; it only ever
  returns a ranked report for a human to act on. Advanced analytics
  (`packages/analytics/overview.py`) is pure read-side aggregation over data
  every earlier phase already writes: equity curve, trade stats, drawdown,
  opportunity-tier distribution, pattern leaderboard, regime distribution —
  no new computation engine, no fabricated numbers.

Live trading is still out of scope — **every order is `is_paper = true`; no
broker/exchange adapter is registered; nothing in this repo can send a live order
or read a real broker/exchange key.**

**Post-Phase-7 security hardening:** an independent security review (see
`docs/blueprint/12-roadmap.md`'s "Hardening de segurança" section) found and
fixed 3 real gaps — ~30 read endpoints missing the auth the API spec already
required, insecure hardcoded default secrets with no startup guard, and
wildcard CORS. All three are fixed and live-verified; see that section for
details.

**Post-Phase-7 Supervisor 24/7:** the worker loop's own liveness is now
honestly observable — a heartbeat (`packages/shared/worker_health.py`)
written once per full loop iteration, `/api/system/health`'s new `worker`
component reporting `red`/`green` off that heartbeat's staleness, per-cadence
try/except isolation so one failing cadence (e.g. news) can't stop the
others, and a threshold-based `Alert` when a cadence fails 3 times in a row.
Docker Compose's long-running services now carry `restart: unless-stopped`.
Live-verified: health flips red→green as a real worker process starts, and
the heartbeat advances across two consecutive real cycles. See
`docs/blueprint/12-roadmap.md`'s "Supervisor 24/7" section for details.

**Dashboard: kill switch button.** The dashboard was previously read-only —
`/api/system/kill-switch` and `/kill-switch/release` existed since Phase 3
but had no UI, so pulling the kill switch meant a manual `curl` with a
Bearer token. The Risk State panel now has a confirm-gated button wired
through a server-side proxy route (`app/api/kill-switch/route.ts`, same
pattern as the existing logout route — the token stays in an httpOnly
cookie, never reaches the browser). Verified end-to-end with a real
Chromium browser against the production build: trigger → dashboard reflects
disabled state → release → back to enabled, with real `Alert`/`AuditLog`
rows written by each click. See `docs/blueprint/12-roadmap.md` for details.

**Dashboard: backtest launcher.** Same gap, different endpoint — the
Backtests panel told you to `POST /api/backtests` via `curl` when empty.
Added a small form (strategy/asset/date-range/capital, `1m` timeframe only
since that's the one with real backfilled history) behind the same
server-side proxy pattern. Live-verified: a real browser run created a real
`BacktestRun` row, confirmed directly in Postgres. Walk-forward/optimize
still API-only — out of scope for this pass.

**Dashboard: restore/promote strategy.** Third and last admin-only action
closed this session — the Strategy Health panel showed lifecycle state and
promotion readiness but had no button for `POST /api/strategies/{id}/restore`
(Phase 5) or `/promote` (Phase 6). Added a confirm-gated
`StrategyActionButton`, shown only when the action actually applies
(Restore under quarantine, Promote when eligible). Live-verified by putting
a real strategy into quarantine and clicking Restore in a real browser:
`StrategyRow.lifecycle_stage` flipped to `paper` and a real `AuditLog` row
was written, confirmed directly in Postgres.

**Market Data Engine + Market Scanner.** Structured candle validation
(`packages/data/validation.py` — OHLC coherence, timeframe-scaled
staleness, absurd single-bar moves), a 0-100 data-quality score
(`packages/data/quality.py`, distinct from the existing
high/degraded/unavailable tag), and a Market Scanner
(`packages/quant/market/events.py`) that turns each candle into
`PRICE_MOVEMENT`/`VOLUME_SPIKE`/`VOLATILITY_SPIKE`/`BREAKOUT_CANDIDATE`/
`MOMENTUM_CHANGE`/`TREND_CHANGE`/`ANOMALY`/`INVALID_MARKET_DATA` candidates
(never trade signals) — deliberately distinct from the existing Pattern
Engine, which classifies setups for scoring rather than doing raw
real-time surveillance. `apps/worker/scanner.py` now isolates each asset in
its own try/except and debounces market-condition alerts
(`apps/worker/market_alerts.py`). New `/api/market/*` endpoints
(`overview`, `assets`, `{symbol}`, `{symbol}/ohlcv`, `events`,
`data-quality`) and two new dashboard panels — Market Overview (with an
explicit `DATA SOURCE: MOCK`/`LIVE MARKET DATA` banner, never mixed
silently) and Recent Market Events. No real Crypto/Forex/Stock provider
adapters were added — no real market-data credentials exist in this
environment, and an untestable stub adapter would be worse than the
existing honest `MockMarketDataProvider` fallback. Live-verified: two
consecutive real worker cycles produced 17 and 18 real events against real
Postgres (proving continuous operation), and both new dashboard panels
render real data in a live browser test. See
`docs/blueprint/12-roadmap.md`'s "PROMPT 2" section for details.

**Pattern/Strategy/Opportunity confidence & evidence.** The Pattern Engine,
Strategy Engine, and Opportunity Scoring Engine already existed from this
repo's real Phase 2/4; this pass closed the gaps a point-by-point spec
review found. Patterns now carry `confidence` (data-quality trustworthiness)
separate from `strength` (magnitude) — never conflated. `detect_breakout`
differentiates CONFIRMED_BREAKOUT from POSSIBLE_BREAKOUT instead of
silently dropping unconfirmed ones. Every strategy gained
`get_risk_profile()`. Opportunities now carry their own `confidence`
(`packages/quant/scoring/inputs.py`'s `compute_opportunity_confidence()` —
data quality, regime confidence, aligned-pattern confidence, whether
`historical_edge` had a real sample), shown separately from `final_score`
everywhere, with an explicit `insufficient_history` flag instead of a
silent neutral score. `/api/opportunities/{id}` now returns structured
`evidence` (`packages/quant/scoring/evidence.py` — deterministic
confirm/warning items from already-computed score components, never a
model's private reasoning), and the dashboard's Top Opportunities table is
click-to-expand into a "why this opportunity exists" panel. A real
strategy-cycle also now emits an `OPPORTUNITY_CREATED` MarketEvent for
every signal scoring above "ignore". Live-verified against real Postgres
and a real browser click-through. See `docs/blueprint/12-roadmap.md`'s
"PROMPT 3" section for details, including which spec divergences (tier/
signal-status naming) were deliberately left alone as cosmetic-only.

**Risk Engine/Portfolio Intelligence hardening.** The Risk Engine, Safety
Belts, Position Sizing, and Correlation Guard already existed from this
repo's real Phase 3; this pass closed the gaps a point-by-point spec review
found, plus one bug the review surfaced. `refresh_snapshot()` — the sole
writer of portfolio history — is now genuinely called every worker cycle
(not just on a fill) and always with the real current `safety_belt_level`
(both fill call-sites were silently defaulting to `"normal"`). Strategy
Health (`packages/quant/learning`'s `health_score`, built in this repo's
real Phase 5) now actually reaches the Risk Engine's decision pipeline —
a degraded strategy gets its size cut in half, a quarantine-level one is
blocked as a defense-in-depth check. Safety Belt size multipliers moved
from a hardcoded Python dict into `config/risk_limits.yaml`
(`safety_belt_multipliers`), and the DEFENSIVE belt state — which
previously triggered at the exact same threshold as the hard daily-loss
block, making its "reduce size" action dead code — now triggers at 70% of
that limit, so it genuinely reduces risk before the hard stop. Monthly
P&L/loss tracking was added (derived, like weekly already was — no new
column). `refresh_correlation_matrix()` — defined since Phase 3 but never
actually called — now runs every strategy cycle, feeding a new Risk Center
dashboard panel (Risk State, Daily/Weekly/Monthly P&L, Drawdown, Exposure,
Available Cash) and a Risk Heatmap visualizing concentration by
asset/strategy/direction/correlation. `GET /api/risk`'s decisions now carry
a `decision` (`approved`/`reduced`/`blocked`), a `reasons` list, and
`risk_amount`/`position_size`/`risk_reward` — API-layer enrichment, no
column renames. Live-verified against real Postgres (a real worker run
produced 50+ real pairwise correlations and real exposure/risk-decision
data) and a real browser click-through of the new Risk Center. See
`docs/blueprint/12-roadmap.md`'s "PROMPT 4" section for the full list,
including the mathematically-validated €10,000 drawdown simulation test.

**News Intelligence Center.** News ingestion + LLM interpretation already
existed from this repo's real Phase 4; this pass built the deterministic
analysis layer the spec asked for on top of it — new `packages/quant/news/`
package: entity extraction (a curated dictionary, never an invented match),
direct-vs-indirect asset mapping, a sentiment lexicon deliberately
independent of the LLM's price-direction call (`docs/sentiment.md`),
deduplication/clustering with source-consensus and conflicting-source
detection, novelty decay, importance classification, a configurable impact
score (`config/news_weights.yaml`), and Event Reaction Memory (real
historical price reactions, gated on a minimum sample like every other
"how confident are we" score in this codebase). A new Macro Calendar
provider abstraction (`docs/macro-events.md`) tracks scheduled releases and
computes surprise the moment `actual` appears, never before. The one rule
that mattered most: a `News Risk Guard` (`docs/event-risk.md`) is the
*only* way News Intelligence touches a trade — wired into
`packages/risk/engine.py` as one more check step that can only reduce size
or block, exactly like every other check, never approve or size on its
own — verified both by a full escalation simulation and by walking the
News Intelligence package's own AST to confirm it never imports
`packages.execution`. A technical/news direction conflict now measurably
lowers Opportunity confidence instead of being silently ignored. New
`GET /api/news/risk`, `GET /api/macro`, `GET /api/news/context/{symbol}`
endpoints and a "News Intelligence Center" dashboard panel (Event Risk,
Market Sentiment, News Momentum, Source Quality, Upcoming Macro Events).
Live-verified against real Postgres and a real browser click-through. See
`docs/blueprint/12-roadmap.md`'s "PROMPT 6" section for the full list,
including the documented, deliberate choice to keep this as worker
cadences (this codebase's established architecture) rather than the
spec's literal six separate processes.

## Architecture at a glance

```text
apps/
  api/         FastAPI backend (auth, system health, assets, market data, portfolio,
               strategies, opportunities/signals, regime, risk, positions/orders/trades,
               news, macro, patterns, learning, research, backtests, alerts, analytics)
  worker/      24/7 loop: Market Data Agent (scan), Trade Monitor + safety-belt
               refresh + Learning Agent (per trade close, every scan), News
               Intelligence Agent (ingestion + DET analysis, own cadence),
               Macro Calendar Worker (own cadence), Sentiment Worker (shift
               detection, own cadence), Strategy Engine cycle (history
               backfill, regime, patterns, strategies, scoring, Risk Engine, paper
               execution), Research Agent + News Learning (own, longer cadence),
               Alert delivery cycle (own cadence)
  dashboard/   Next.js dashboard (single admin user)
packages/
  shared/      DB models, settings, logging, OHLCV lookup — shared across apps/packages
  data/        Market data + news provider interfaces, mock providers for both
  quant/       indicators, regime classifier, pattern detectors, pluggable
               strategies (constructor-parameterized), scoring engine, learning
               (strategy stats/health score, quarantine, research/rule validation,
               market memory, degradation analysis, promotion pipeline)
  portfolio/   equity/cash/exposure/drawdown computation, append-only snapshot ledger
  risk/        position sizing, correlation guard, safety belts, the veto-power decision pipeline
  execution/   ExecutionProvider interface, PaperExecutionProvider, order manager,
               shared fill-simulation math (packages/execution/fills.py)
  backtest/    event-driven Backtest Engine, isolated simulated portfolio,
               walk-forward validation, parameter-stability checks, bounded
               grid-search parameter optimization — never touches the live
               paper account, never writes a strategy's live parameters
  notifications/ NotificationChannel Protocol, Email/Telegram channels, an
               honest WhatsApp stub, and a fan-out dispatcher — never decides,
               only delivers
  analytics/   read-only aggregation over existing data — equity curve, trade
               stats, drawdown, tier/regime distributions, pattern leaderboard
  llm/         Anthropic API client + News Intelligence/Learning/Research
               interpretation — never imported by packages/execution (structural
               "LLM ≠ Trading Engine")
infra/
  docker/      docker-compose + Dockerfiles
  migrations/  Alembic
scripts/       seed.py — admin user, asset universe, paper portfolio, strategy registry
config/        risk_limits.yaml, scoring_weights.yaml, promotion_criteria.yaml — all
               live-editable (risk limits via PATCH /api/system/risk-limits)
docs/blueprint/  full technical spec (architecture, DB schema, API, agents,
                 event flow, memory, scoring, risk engine, dashboard spec,
                 backtesting, LLM prompts, roadmap)
```

## Running it

### With Docker (recommended)

```bash
cp .env.example .env   # edit ADMIN_PASSWORD / JWT_SECRET to real values —
                        # the app refuses to start on the placeholder
                        # defaults (packages/shared/settings.py)
                        # optionally set ANTHROPIC_API_KEY to enable real
                        # news interpretation — leave empty and it still
                        # works, just without that one capability
docker compose -f infra/docker/docker-compose.yml up --build
```

- API: http://localhost:8000 (docs at `/docs`)
- Dashboard: http://localhost:3000 (redirects to `/login`)

All three images run as a non-root user. `docker compose config` validates,
but the full `up --build` hasn't been run in this repo's own dev sandbox (no
Docker daemon available there) — worth a one-time check before relying on it.

The `migrate` service applies Alembic migrations and runs `scripts/seed.py`
(creates the admin user, seeds ~20 assets across crypto/forex/equities/indices/
commodities, the initial €10,000 paper portfolio, and registers the 4 Phase 2
strategies) before `api`/`worker` start. The worker backfills enough mock history
per asset on startup so opportunities show up within the first strategy cycle
rather than after `MIN_CANDLES_REQUIRED` real minutes.

Backtests, walk-forward runs, and parameter optimization are launched via the API
(no dashboard launcher UI yet — the dashboard's Backtests panel is read-only) —
use `/docs` for an interactive form, or:
```bash
curl -X POST localhost:8000/api/backtests -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id":1,"asset_id":1,"timeframe":"1m","start_ts":"...","end_ts":"...","initial_capital":10000}'

curl -X POST localhost:8000/api/backtests/optimize -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id":1,"asset_id":1,"timeframe":"1m","start_ts":"...","end_ts":"...","window_days":1,"initial_capital":10000}'
```
Results are only as deep as the OHLCV history this deployment has actually
collected — there's no separate historical dataset (see
`docs/blueprint/12-roadmap.md`'s Phase 6/7 sections). Optimization always
returns a ranked report (`best_params` is `null` when no candidate passes the
walk-forward consistency bar) — nothing is ever applied automatically to a
strategy's live defaults.

Alert delivery (email/Telegram) needs the `SMTP_*`/`TELEGRAM_*` settings in
`.env` (see `.env.example`); with none configured, alerts still get a
`delivered_at` timestamp on every attempt and an honest `not_configured`
status per channel in `alerts.meta["_delivery"]`.

### Locally, without Docker

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # point DATABASE_URL at a local Postgres 16, and set
                        # real ADMIN_PASSWORD/JWT_SECRET values — every
                        # component (including `alembic`) refuses to start
                        # on the placeholder defaults
alembic upgrade head
python -m scripts.seed
uvicorn apps.api.main:app --reload &
python -m apps.worker.main &

# Tests
pytest

# Dashboard
cd apps/dashboard && npm install && npm run dev
```

## Continuous Integration

`.github/workflows/ci.yml` runs on every push/PR: `ruff check .` (real bugs —
unused imports, undefined names, mutable-default footguns — not a style
rewrite; see `[tool.ruff]` in `pyproject.toml`), `mypy packages apps scripts`
(type-checked with the `pydantic.mypy` plugin so FastAPI response models
type-check correctly), then the full pytest suite (494 tests) against a real
`postgres:16-alpine` service container, migrated from scratch via `alembic
upgrade head`; separately, the dashboard's `eslint` + `next build`; and
separately again, a plain `docker build` of all three
`infra/docker/Dockerfile.*` images — the only place those get built at all,
since this repo's own dev sandbox has no Docker daemon. Nothing in CI
touches a broker, an exchange, or real capital — it only proves the
existing test/build/lint/type-check/image-build steps that were previously
run by hand (or, for the Docker images, not run at all) still pass.

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
