from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import AnalyticsOverviewOut
from packages.analytics.overview import build_analytics_overview
from packages.shared.models import AdminUser

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewOut)
def get_analytics_overview(
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> AnalyticsOverviewOut:
    overview = build_analytics_overview(db)
    return AnalyticsOverviewOut(
        equity_curve=[{"ts": p.ts, "equity": p.equity, "drawdown_pct": p.drawdown_pct} for p in overview.equity_curve],
        trade_stats=overview.trade_stats,
        drawdown=overview.drawdown,
        tier_distribution=overview.tier_distribution,
        pattern_leaderboard=overview.pattern_leaderboard,
        regime_distribution=overview.regime_distribution,
    )
