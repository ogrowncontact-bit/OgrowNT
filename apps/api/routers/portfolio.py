from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import (
    CorrelationPairOut,
    ExposureItem,
    PortfolioExposureOut,
    PortfolioResponse,
    PortfolioSnapshotOut,
)
from packages.portfolio.state import compute_state
from packages.shared.models import AdminUser, Asset, CorrelationMatrixEntry, PortfolioSnapshot, StrategyRow

router = APIRouter(tags=["portfolio"])


@router.get("/api/portfolio", response_model=PortfolioResponse)
def get_portfolio(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> PortfolioResponse:
    latest = db.execute(
        select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(1)
    ).scalar_one_or_none()
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No portfolio snapshot yet — run scripts/seed.py",
        )
    # weekly/monthly are never persisted per-row (same reasoning as before
    # Prompt 4: cheap to re-derive from the portfolio_snapshots equity
    # history on every read) — computed fresh here, pinned to the same cash
    # the persisted snapshot recorded so the two stay consistent.
    state = compute_state(db, cash=latest.cash)
    return PortfolioResponse(
        equity=latest.equity,
        cash=latest.cash,
        exposure_pct=latest.exposure_pct,
        daily_pnl=latest.daily_pnl,
        drawdown_pct=latest.drawdown_pct,
        safety_belt_level=latest.safety_belt_level,
        as_of=latest.ts,
        weekly_pnl=state.weekly_pnl,
        weekly_loss_pct=state.weekly_loss_pct,
        monthly_pnl=state.monthly_pnl,
        monthly_loss_pct=state.monthly_loss_pct,
    )


@router.get("/api/portfolio/exposure", response_model=PortfolioExposureOut)
def get_portfolio_exposure(
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> PortfolioExposureOut:
    """Risk Center concentration breakdown (Prompt 4 §31 Risk Heatmap):
    exposure by asset/strategy/direction from currently open positions, plus
    the most recent pairwise correlation for any asset currently held
    (packages/risk/correlation_guard.py's refresh_correlation_matrix, run by
    the worker's strategy cadence)."""
    state = compute_state(db)
    equity = state.equity

    by_asset: dict[str, float] = {}
    by_strategy: dict[str, float] = {}
    by_direction: dict[str, float] = {}
    for position in state.open_positions:
        notional = position.entry_price * position.size
        asset = db.get(Asset, position.asset_id)
        strategy = db.get(StrategyRow, position.strategy_id) if position.strategy_id else None
        if asset is not None:
            by_asset[asset.symbol] = by_asset.get(asset.symbol, 0.0) + notional
        if strategy is not None:
            by_strategy[strategy.code] = by_strategy.get(strategy.code, 0.0) + notional
        by_direction[position.direction] = by_direction.get(position.direction, 0.0) + notional

    def _items(breakdown: dict[str, float]) -> list[ExposureItem]:
        return [
            ExposureItem(
                key=key, notional=round(notional, 2),
                pct_of_equity=round(notional / equity * 100, 4) if equity > 0 else 0.0,
            )
            for key, notional in sorted(breakdown.items(), key=lambda kv: -kv[1])
        ]

    held_asset_ids = {p.asset_id for p in state.open_positions}
    correlations: list[CorrelationPairOut] = []
    if held_asset_ids:
        rows = (
            db.query(CorrelationMatrixEntry)
            .filter(
                or_(
                    CorrelationMatrixEntry.asset_id_a.in_(held_asset_ids),
                    CorrelationMatrixEntry.asset_id_b.in_(held_asset_ids),
                )
            )
            .order_by(CorrelationMatrixEntry.ts.desc())
            .all()
        )
        seen_pairs: set[tuple[int, int]] = set()
        for row in rows:
            pair = (row.asset_id_a, row.asset_id_b)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            asset_a = db.get(Asset, row.asset_id_a)
            asset_b = db.get(Asset, row.asset_id_b)
            if asset_a is not None and asset_b is not None:
                correlations.append(
                    CorrelationPairOut(
                        asset_symbol_a=asset_a.symbol, asset_symbol_b=asset_b.symbol,
                        correlation=row.correlation, ts=row.ts,
                    )
                )

    return PortfolioExposureOut(
        equity=equity, by_asset=_items(by_asset), by_strategy=_items(by_strategy),
        by_direction=_items(by_direction), correlations=correlations,
    )


@router.get("/api/portfolio/history", response_model=list[PortfolioSnapshotOut])
def get_portfolio_history(
    limit: int = 500, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> Sequence[PortfolioSnapshot]:
    return (
        db.execute(select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(limit))
        .scalars()
        .all()
    )


