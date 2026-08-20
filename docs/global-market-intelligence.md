# Global Market Intelligence & 24/7 Opportunity Discovery ("PROMPT 11")

## The central constraint

> O scanner: NUNCA executa trades. Ele somente produz: MARKET INFORMATION,
> OPPORTUNITIES, ALERTS.

Every module in `packages/market/` and `apps/worker/market_intelligence.py`
respects this boundary structurally: none of them import
`packages.execution`, none of them create an `Order` or a `Position`, and
the only thing they ever write toward a `Signal` is metadata
(`opportunity_type`/`fingerprint`/`expires_at`) — never its price, size, or
status. The Risk Engine and Execution Engine remain the only sovereign
paths to a real (paper) fill, exactly as before this package existed.

The second constraint that shapes every scoring number in this package:

> SCORE ≠ PROBABILIDADE — Não interpretar: Opportunity Score 80 como: 80%
> chance of profit.

`OpportunityScore.confidence` (Phase 2/3) already keeps this distinction
explicit; every new score this phase adds (`LiquidityAssessment.score`,
`InitialOpportunityScore.score`, `AnomalyFinding.score`,
`VolatilityReading.percentile`) is a 0-100 *evidence* number, documented
as such, never presented as a win probability.

## Why this phase is mostly a thin new layer

A very large fraction of what "PROMPT 11" asks for already existed before
this phase started:

| Prompt 11 asks for | Already existed as |
|---|---|
| Multi-asset-class universe | `Asset` + `MockMarketDataProvider` + 22-asset seed (crypto/forex/equity/index/commodity) |
| "Opportunity" object | `Signal` + `OpportunityScore` (~90% field overlap) |
| Cross-asset correlation | `CorrelationMatrixEntry` + `packages/risk/correlation_guard.py::refresh_correlation_matrix` |
| EconomicEvent | `MacroEvent` (Prompt 6) |
| Anomaly/cross-asset detection | `packages/quant/patterns/detector.py::detect_anomaly`/`detect_cross_asset` (existed, never wired to anything) |
| Historical analog | `packages/quant/learning/memory.py` (Phase 5 Market Memory) |
| Volatility/volume math | `packages/quant/indicators/core.py::atr`/`realized_volatility`/`trend_strength`/`avg_volume` |

The genuinely new work this phase adds is the orchestration, persistence,
and classification layer on top of that — `packages/market/`'s 14
modules, two new worker cadences, one new API router, and one new
dashboard panel.

## The pipeline

```
MarketUniverseManager (universe.py)           packages/data/quality.py
  DISCOVERED -> DATA VALIDATION ->                     |
  LIQUIDITY VALIDATION -> CLASSIFICATION ->     liquidity.py's
  PAPER ELIGIBLE                                score_liquidity()
        |
        v
FastMarketScanner (fast_scanner.py) -- cheap composite score,
  runs across the WHOLE paper-eligible universe, keeps the Top-N
        |
        v  (only the Top-N reach here)
apps/worker/market_intelligence.py orchestrates, per asset:
  structure.py (swing points, BOS/CHoCH)
  volatility.py (percentile, regime transitions -> VolatilityEvent)
  anomaly.py (5 detectors -> Anomaly)
  multi_timeframe.py (resampled 1m->5m/15m/1h/4h/1D agreement/conflict)
        |
        v
opportunity_types.py classifies the asset's open Signal (from
  apps/worker/strategy_runner.py's existing pipeline) into the closed
  12-value vocabulary, computes fingerprint + expires_at
        |
        v
clustering.py groups same-direction correlated Signals (reusing the
  persisted correlation matrix) -> OpportunityCluster + ranking_penalty
        |
        v
ranking.py: final_score (existing, risk-adjusted) x (1 - cluster penalty)
  = risk-adjusted attractiveness, NOT raw return potential
```

`watchlist.py`'s `DynamicWatchlist` is auto-managed alongside this same
pass (anomaly/volatility findings and high fast-scan volume all trigger an
entry); `pairs.py` and `historical_analog.py` are deliberately **not**
part of this periodic pipeline — see below.

## Modules

| Module | Responsibility |
|---|---|
| `packages/market/sessions.py` | `MarketSessionEngine` + `GlobalMarketClock` — 6 named exchange sessions via `zoneinfo`, forex's 24/5 continuity, named overlap detection |
| `packages/market/liquidity.py` | 0-100 score + TIER_A/B/C/UNTRADABLE from a cross-asset volume percentile + data quality — no order book anywhere in this codebase, `OrderBookSnapshot` is an optional additive input for later |
| `packages/market/universe.py` | `MarketUniverseManager` — the DISCOVERED→PAPER ELIGIBLE pipeline, quarantine on repeated corrupted-feed events |
| `packages/market/fast_scanner.py` | `FastMarketScanner` — cheap composite `InitialOpportunityScore` across the whole universe, Top-N cutoff before anything heavier runs |
| `packages/market/multi_timeframe.py` | Honest resampling of real 1m OHLCV into 5m/15m/1h/4h/1D (the mock provider's own "native" multi-timeframe output is mislabeled — see below); explicit, never-hidden `TIMEFRAME_CONFLICT` |
| `packages/market/structure.py` | Fractal swing-point detector, HH/HL/LH/LL structure classification, BREAK_OF_STRUCTURE vs CHANGE_OF_CHARACTER |
| `packages/market/volatility.py` | Percentile-ranked realized volatility vs an asset's own history, regime labeling, transition-only persistence (not a tick-by-tick log) |
| `packages/market/anomaly.py` | `AnomalyScanner` — 5 of 6 closed types backed by real detection, `spread_expansion` never emitted (no order book) |
| `packages/market/opportunity_types.py` | Pure classifier for the closed 12-value OPPORTUNITY TYPES vocabulary; geometric (log-space) fingerprint bucketing; per-type `expires_at` |
| `packages/market/clustering.py` | Union-find over the persisted correlation matrix, same-direction only, proportional ranking penalty |
| `packages/market/historical_analog.py` | Thin wrapper over Phase 5 Market Memory, adds sample-size-aware quality + real realized-P&L stats, fixed "not a prediction" disclaimer |
| `packages/market/pairs.py` | Spread/hedge-ratio/z-score + an honestly-labeled mean-reversion heuristic (not a real cointegration test) — on-demand only, never a periodic cadence |
| `packages/market/watchlist.py` | `DynamicWatchlist` — one row per asset, auto add/refresh/decay |
| `packages/market/ranking.py` | `OpportunityRankingEngine` — risk-adjusted ranking, proportional cluster-penalty discount |
| `apps/worker/market_intelligence.py` | Orchestrates the modules above into two worker cadences |

## The multi-timeframe honesty problem

`MockMarketDataProvider.get_recent_candles(symbol, timeframe, limit)`
ignores the `timeframe` argument for bucketing purposes — every "bar" it
returns is really one minute wide no matter what timeframe string is
requested (see the provider's own docstring). Trusting its 5m/15m/1h/4h/1D
output directly would have been a fabricated-data bug, not a feature.
`multi_timeframe.py::resample_candles` instead aggregates the *real*,
already-persisted 1m OHLCV history into genuine higher-timeframe bars
(standard open=first/high=max/low=min/close=last/volume=sum), and only
emits a bar for a bucket with a complete set of 1m candles — a partial
trailing bucket is dropped, never faked. This also means the module works
unchanged once a real market data provider replaces the mock.

## Compute isolation

`packages/market/pairs.py` is deliberately **not** wired into a periodic
worker cadence: there's no dedicated table for its output (an "economy of
tables" choice — see `packages/shared/models.py`'s Prompt-11 section
comment), so running it on a clock would be wasted compute with nowhere
to land. It's exposed on demand instead, from `GET /api/global-market/pairs`.

The two new cadences (`universe_interval_seconds`,
`market_intelligence_interval_seconds`) run inside the single existing
`apps/worker` process, the same "single process, multiple independently-
cadenced logical workers" divergence established since Phase 2 and reused
in every prompt since — not the 13 separate OS processes a literal
reading of §92 would imply. Three of those 13 named workers
(EconomicCalendarWorker/NewsScannerWorker/AlertWorker) already existed as
the macro/news/alert-delivery cadences before this phase.

## API and dashboard

`GET /api/global-market/*` (`apps/api/routers/global_market.py`) —
deliberately a new prefix for the genuinely new endpoint groups
(universe/volatility/anomalies/watchlist/clusters/sessions/structure/
pairs/historical-analog). `GET /api/opportunities` and `GET /api/regime`
were extended in place with `opportunity_type`/`fingerprint`/`expires_at`
rather than duplicated; `/api/economic-events` and `/api/alerts` were
already covered by the existing `/api/macro` and `/api/alerts` endpoints.

The dashboard's "Global Market Command Center" panel
(`components/GlobalMarketCommandCenter.tsx`) deliberately does not
duplicate sections that already exist elsewhere (Top Opportunities,
Market Regimes, News, Macro Events, Correlation Map, Portfolio Exposure,
and Risk all have their own panels already) — it covers only what's
genuinely new: the asset universe's health/liquidity standing, the
Dynamic Watchlist, recent anomalies, volatility regime transitions,
correlated-opportunity clusters, and the global session clock.

## Testing

`tests/test_market_*.py` — unit coverage for every module above (168
tests total), `tests/test_worker_market_intelligence.py` (the full
orchestration, including a hand-verified BREAKOUT classification against
a known zigzag), `tests/test_global_market_api.py` (every endpoint, real
login), and `tests/test_market_stress_and_scale.py` (a 150-synthetic-asset
smoke test, per-asset engine-failure isolation, the
universe-ineligibility→fast-scanner-exclusion cross-module contract,
fingerprint dedup, and forex weekend closure).
