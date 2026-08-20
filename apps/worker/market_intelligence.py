"""Global Market Intelligence cadence -- "PROMPT 11" §92.

Composes packages/market/*'s engines into the fast-scan -> deep-scan-on-
the-top-N pipeline the prompt describes (§6-7). This module never creates
a Signal itself -- that stays apps/worker/strategy_runner.py's job
(the existing Strategy/Pattern/Regime/Opportunity Scoring pipeline). It
only:

  1. runs the cheap FastMarketScanner across the whole paper-eligible
     universe and keeps its Top-N,
  2. runs the heavier per-asset engines (structure/volatility/anomaly/
     multi-timeframe) on just that Top-N,
  3. auto-manages the Dynamic Watchlist from what those engines find,
  4. enriches whatever Signal strategy_runner already created for that
     asset with an opportunity_type/fingerprint/expires_at classification,
  5. clusters same-direction correlated open Signals and persists the
     result for the ranking layer (packages/market/ranking.py).

The scanner NEVER executes a trade (§95) -- every function below only
reads market data and writes market-intelligence rows (VolatilityEvent/
Anomaly/OpportunityCluster/WatchlistEntry/Signal metadata columns), never
an order, a position, or anything packages/execution would act on.

packages/market/pairs.py is deliberately NOT wired into a periodic cadence
here: with no dedicated table for its output (an "economy of tables"
choice -- see packages/shared/models.py's Prompt-11 section comment),
running it on a clock would just be wasted compute with nowhere to land.
It's exposed on-demand instead, from `GET /api/global-market/pairs`
(apps/api/routers/global_market.py).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.data.connectors.market.base import MarketDataProvider
from packages.market.anomaly import ANOMALY_NEWS_SHOCK, AnomalyScanner
from packages.market.clustering import OpportunityCandidate, find_clusters, persist_clusters
from packages.market.fast_scanner import FastMarketScanner
from packages.market.multi_timeframe import MultiTimeframeEngine
from packages.market.opportunity_types import (
    OpportunityEvidence,
    classify_opportunity_type,
    compute_expiration,
    compute_fingerprint,
)
from packages.market.structure import MarketStructureEngine
from packages.market.universe import MarketUniverseManager
from packages.market.volatility import EVENT_COLLAPSE, EVENT_SPIKE, VolatilityEngine
from packages.market.watchlist import REASON_ANOMALY, REASON_VOLATILITY, REASON_VOLUME, DynamicWatchlist
from packages.shared.models import Signal

logger = logging.getLogger("worker.market_intelligence")

# FastMarketScanner's "volume" component (0-100) above which an asset's
# volume activity alone is worth a watchlist entry, independent of
# whatever the heavier anomaly/volatility engines separately find.
_VOLUME_WATCHLIST_SCORE = 80.0

# Signal statuses that still represent a live, actionable opportunity --
# used both to pick clustering candidates and to decide which Signal (if
# any) gets this cycle's opportunity_type enrichment.
_OPEN_SIGNAL_STATUSES = ("pending", "scored", "approved")


def run_universe_cycle(db: Session, provider: MarketDataProvider) -> dict:
    evaluations = MarketUniverseManager().run_universe_evaluation_cycle(db, provider)
    transitions = [e for e in evaluations if e.previous_status != e.status]
    return {"evaluated": len(evaluations), "transitions": len(transitions)}


def _latest_open_signal(db: Session, asset_id: int) -> Signal | None:
    return (
        db.query(Signal)
        .filter(Signal.asset_id == asset_id, Signal.status.in_(_OPEN_SIGNAL_STATUSES))
        .order_by(Signal.ts.desc())
        .first()
    )


def _enrich_signal_with_opportunity_type(db: Session, signal: Signal, opportunity_type: str | None, *, now: datetime) -> None:
    if opportunity_type is None or signal.opportunity_type is not None:
        return  # honestly nothing to classify, or already classified this lifetime
    signal.opportunity_type = opportunity_type
    signal.fingerprint = compute_fingerprint(
        signal.asset.symbol, opportunity_type, signal.direction, signal.entry_price, now=now,
    )
    signal.expires_at = compute_expiration(opportunity_type, now=now)
    db.commit()


def run_market_intelligence_cycle(db: Session, *, top_n: int = 20, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    fast_scanner = FastMarketScanner()
    structure_engine = MarketStructureEngine()
    volatility_engine = VolatilityEngine()
    anomaly_scanner = AnomalyScanner()
    mtf_engine = MultiTimeframeEngine()
    watchlist = DynamicWatchlist()

    top = fast_scanner.scan(db, top_n=top_n, now=now)
    candidates: list[OpportunityCandidate] = []
    anomalies_found = 0
    volatility_events_found = 0

    for score in top:
        try:
            structure_reading = structure_engine.analyze(db, score.asset_id, score.symbol)
            volatility_reading = volatility_engine.analyze(db, score.asset_id, score.symbol, now=now)
            mtf_reading = mtf_engine.analyze(db, score.asset_id, score.symbol)
            findings = anomaly_scanner.scan_asset(db, score.asset_id, score.symbol, now=now)
        except Exception:  # noqa: BLE001 - one asset's failure must not stop the batch
            logger.exception("Market intelligence pass failed for asset_id=%s", score.asset_id)
            continue

        if findings:
            anomalies_found += len(findings)
            watchlist.add_or_refresh(db, score.asset_id, REASON_ANOMALY, now=now)
        if volatility_reading.event_type in (EVENT_SPIKE, EVENT_COLLAPSE):
            volatility_events_found += 1
            watchlist.add_or_refresh(db, score.asset_id, REASON_VOLATILITY, now=now)
        if score.components.get("volume", 0.0) >= _VOLUME_WATCHLIST_SCORE:
            watchlist.add_or_refresh(db, score.asset_id, REASON_VOLUME, now=now)

        news_shock = any(f.anomaly_type == ANOMALY_NEWS_SHOCK for f in findings)
        evidence = OpportunityEvidence(
            structure=structure_reading.structure, break_state=structure_reading.break_state,
            volatility_event_type=volatility_reading.event_type, timeframe_agreement=mtf_reading.agreement_state,
            range_position=score.components.get("range_position"), news_shock=news_shock,
        )
        classification = classify_opportunity_type(evidence)

        signal = _latest_open_signal(db, score.asset_id)
        if signal is not None:
            _enrich_signal_with_opportunity_type(db, signal, classification.opportunity_type, now=now)
            candidates.append(
                OpportunityCandidate(
                    signal_id=signal.id, asset_id=score.asset_id, symbol=score.symbol, direction=signal.direction,
                )
            )

    clusters = find_clusters(db, candidates)
    persist_clusters(db, clusters, now=now)
    watchlist.decay_stale_entries(db, now=now)

    return {
        "scanned": len(top), "anomalies_found": anomalies_found, "volatility_events_found": volatility_events_found,
        "clusters_found": len(clusters),
    }
