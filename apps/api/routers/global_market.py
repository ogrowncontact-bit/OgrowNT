"""Global Market Intelligence API -- "PROMPT 11" §91.

Deliberately a new `/api/global-market/*` prefix for the genuinely new
endpoint groups (universe/volatility/anomalies/watchlist/clusters/sessions/
structure/pairs/historical-analog) -- the same "different prefix from an
existing, narrower concept" precedent as Prompt 10's `/api/research-lab`
vs. the older `/api/research`. `GET /api/opportunities` and
`GET /api/regime` (opportunities.py) already cover the prompt's
overlapping endpoints and were extended in place instead of duplicated
here; `GET /api/macro` (news.py) already covers `/api/economic-events`;
`GET /api/alerts` (alerts.py) already covers `/api/alerts`.

Every endpoint here is read-only. The scanner NEVER executes a trade
(§95) -- nothing in this router can create an order, a position, or
anything packages/execution would act on.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import (
    AnomalyOut,
    AssetUniverseOut,
    GlobalMarketSnapshotOut,
    HistoricalAnalogOut,
    MarketSessionOut,
    OpportunityClusterOut,
    PairSignalOut,
    StructureReadingOut,
    VolatilityEventOut,
    WatchlistEntryOut,
)
from packages.market.historical_analog import HistoricalAnalogEngine
from packages.market.pairs import scan_correlated_universe
from packages.market.sessions import GlobalMarketClock
from packages.market.structure import MarketStructureEngine
from packages.market.universe import is_paper_eligible
from packages.market.watchlist import STATUS_ACTIVE as WATCHLIST_ACTIVE
from packages.shared.models import AdminUser, Anomaly, Asset, OpportunityCluster, VolatilityEvent, WatchlistEntry

router = APIRouter(prefix="/api/global-market", tags=["global-market"])


@router.get("/universe", response_model=list[AssetUniverseOut])
def list_universe(
    status_filter: str | None = None, asset_class: str | None = None, limit: int = 200,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[Asset]:
    stmt = select(Asset).order_by(Asset.symbol).limit(limit)
    if status_filter is not None:
        stmt = stmt.where(Asset.status == status_filter)
    if asset_class is not None:
        stmt = stmt.where(Asset.asset_class == asset_class)
    return list(db.execute(stmt).scalars().all())


@router.get("/volatility", response_model=list[VolatilityEventOut])
def list_volatility_events(
    asset_id: int | None = None, limit: int = 50, db: Session = Depends(get_session),
    _: AdminUser = Depends(get_current_admin),
) -> list[VolatilityEvent]:
    stmt = select(VolatilityEvent).order_by(VolatilityEvent.ts.desc()).limit(limit)
    if asset_id is not None:
        stmt = stmt.where(VolatilityEvent.asset_id == asset_id)
    return list(db.execute(stmt).scalars().all())


@router.get("/anomalies", response_model=list[AnomalyOut])
def list_anomalies(
    asset_id: int | None = None, reviewed: bool | None = None, limit: int = 50,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[Anomaly]:
    stmt = select(Anomaly).order_by(Anomaly.ts.desc()).limit(limit)
    if asset_id is not None:
        stmt = stmt.where(Anomaly.asset_id == asset_id)
    if reviewed is not None:
        stmt = stmt.where(Anomaly.reviewed == reviewed)
    return list(db.execute(stmt).scalars().all())


@router.get("/watchlist", response_model=list[WatchlistEntryOut])
def list_watchlist(
    include_removed: bool = False, limit: int = 100, db: Session = Depends(get_session),
    _: AdminUser = Depends(get_current_admin),
) -> list[WatchlistEntry]:
    stmt = select(WatchlistEntry).order_by(WatchlistEntry.updated_at.desc()).limit(limit)
    if not include_removed:
        stmt = stmt.where(WatchlistEntry.status == WATCHLIST_ACTIVE)
    return list(db.execute(stmt).scalars().all())


@router.get("/clusters", response_model=list[OpportunityClusterOut])
def list_clusters(
    limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[OpportunityCluster]:
    stmt = select(OpportunityCluster).order_by(OpportunityCluster.ts.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


@router.get("/sessions", response_model=GlobalMarketSnapshotOut)
def get_global_sessions(_: AdminUser = Depends(get_current_admin)) -> GlobalMarketSnapshotOut:
    """"PROMPT 11" §19-20 -- the New York/London/Frankfurt/Tokyo/Hong Kong/
    Sydney session states plus which named overlaps (e.g. London/New York)
    are active right now. A cheap pure-function computation
    (packages/market/sessions.py) -- no DB read at all.
    """
    snapshot = GlobalMarketClock().snapshot()
    return GlobalMarketSnapshotOut(
        ts=snapshot.ts,
        sessions=[
            MarketSessionOut(
                session=s.session, state=s.state, local_time=s.local_time,
                minutes_to_next_transition=s.minutes_to_next_transition,
            )
            for s in snapshot.sessions
        ],
        active_overlaps=[list(pair) for pair in snapshot.active_overlaps],
    )


@router.get("/structure/{symbol}", response_model=StructureReadingOut)
def get_market_structure(
    symbol: str, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> StructureReadingOut:
    asset = db.execute(select(Asset).where(Asset.symbol == symbol)).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
    reading = MarketStructureEngine().analyze(db, asset.id, asset.symbol)
    return StructureReadingOut(
        symbol=reading.symbol, structure=reading.structure, break_state=reading.break_state,
        range_high=reading.range_high, range_low=reading.range_low, reason=reading.reason,
    )


@router.get("/pairs", response_model=list[PairSignalOut])
def get_pair_signals(
    asset_ids: str | None = None, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[PairSignalOut]:
    """Experimental pairs research (packages/market/pairs.py) -- on-demand
    only, never wired into a periodic worker cadence (see
    apps/worker/market_intelligence.py's module docstring for why). Scans
    a caller-supplied `asset_ids` (comma-separated) subset, or the whole
    paper-eligible universe when omitted.
    """
    if asset_ids is not None:
        try:
            ids = [int(x) for x in asset_ids.split(",") if x.strip()]
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="asset_ids must be comma-separated integers") from exc
    else:
        eligible = db.execute(select(Asset)).scalars().all()
        ids = [a.id for a in eligible if is_paper_eligible(a)]

    signals = scan_correlated_universe(db, ids)
    return [
        PairSignalOut(
            symbol_a=s.symbol_a, symbol_b=s.symbol_b, hedge_ratio=s.hedge_ratio, zscore=s.zscore,
            looks_mean_reverting=s.looks_mean_reverting, autocorrelation=s.autocorrelation,
            sample_size=s.sample_size, disclaimer=s.disclaimer,
        )
        for s in signals
    ]


@router.get("/historical-analog", response_model=HistoricalAnalogOut)
def get_historical_analog(
    regime: str | None = None, pattern_type: str | None = None, direction: str | None = None, k: int = 10,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> HistoricalAnalogOut:
    """"PROMPT 11" §62-63 -- "have I seen a market context like this
    before, and what happened?" Never phrased as a prediction (see
    packages/market/historical_analog.py's module docstring).
    """
    result = HistoricalAnalogEngine().find_analogs(db, regime=regime, pattern_type=pattern_type, direction=direction, k=k)
    return HistoricalAnalogOut(
        sample_size=result.sample_size, win_rate=result.win_rate, outcome_counts=result.outcome_counts,
        realized_pnl_samples=result.realized_pnl_samples, worst_pnl=result.worst_pnl, quality=result.quality,
        disclaimer=result.disclaimer,
    )
