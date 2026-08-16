"""Advanced analytics — docs/blueprint/12-roadmap.md Phase 7's "analytics
avançado". Pure read-side aggregation over data every earlier phase already
writes (portfolio_snapshots, trades, opportunity_scores, pattern_performance,
market_regimes): no new computation engine, no new DB writes. Every field is
a real query result; an empty/insufficient-data case reports an honest empty
list, empty dict, or None — never a fabricated placeholder, same "no
hallucinated data" discipline as packages/quant/scoring/inputs.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from packages.shared.models import MarketRegime, OpportunityScore, PatternPerformance, PortfolioSnapshot, Trade

EQUITY_CURVE_LIMIT = 500
TIER_WINDOW_DAYS = 30
REGIME_WINDOW_DAYS = 7
PATTERN_LEADERBOARD_LIMIT = 20


@dataclass(frozen=True)
class EquityPoint:
    ts: datetime
    equity: float
    drawdown_pct: float


@dataclass(frozen=True)
class TradeStats:
    total_trades: int
    win_rate: float | None
    expectancy: float | None
    profit_factor: float | None
    avg_pnl: float | None


@dataclass(frozen=True)
class DrawdownStats:
    current_drawdown_pct: float | None
    max_drawdown_pct: float | None
    peak_equity: float | None


@dataclass(frozen=True)
class PatternLeaderboardEntry:
    pattern_type: str
    regime: str
    sample_size: int
    win_rate: float | None
    expectancy: float | None


@dataclass(frozen=True)
class AnalyticsOverview:
    equity_curve: list[EquityPoint]
    trade_stats: TradeStats
    drawdown: DrawdownStats
    tier_distribution: dict[str, int]
    pattern_leaderboard: list[PatternLeaderboardEntry]
    regime_distribution: dict[str, int]


def _equity_curve(db: Session, limit: int) -> list[EquityPoint]:
    rows = db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(limit).all()
    rows.reverse()
    return [EquityPoint(ts=r.ts, equity=r.equity, drawdown_pct=r.drawdown_pct) for r in rows]


def _trade_stats(db: Session) -> TradeStats:
    trades = db.query(Trade).all()
    total = len(trades)
    if total == 0:
        return TradeStats(total_trades=0, win_rate=None, expectancy=None, profit_factor=None, avg_pnl=None)

    wins = [t for t in trades if t.outcome == "win"]
    losses = [t for t in trades if t.outcome == "loss"]
    win_rate = len(wins) / total
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None
    r_multiples = [t.r_multiple for t in trades if t.r_multiple is not None]
    expectancy = (sum(r_multiples) / len(r_multiples)) if r_multiples else None
    avg_pnl = sum(t.pnl for t in trades) / total

    return TradeStats(
        total_trades=total,
        win_rate=round(win_rate, 4),
        expectancy=round(expectancy, 4) if expectancy is not None else None,
        profit_factor=round(profit_factor, 4) if profit_factor is not None else None,
        avg_pnl=round(avg_pnl, 4),
    )


def _drawdown_stats(db: Session) -> DrawdownStats:
    latest = db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).first()
    peak_equity = db.query(func.max(PortfolioSnapshot.equity)).scalar()
    max_drawdown = db.query(func.max(PortfolioSnapshot.drawdown_pct)).scalar()
    return DrawdownStats(
        current_drawdown_pct=latest.drawdown_pct if latest else None,
        max_drawdown_pct=max_drawdown,
        peak_equity=peak_equity,
    )


def _tier_distribution(db: Session, window_days: int) -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(OpportunityScore.tier, func.count(OpportunityScore.id))
        .filter(OpportunityScore.created_at >= cutoff)
        .group_by(OpportunityScore.tier)
        .all()
    )
    return {tier: count for tier, count in rows}


def _pattern_leaderboard(db: Session, limit: int) -> list[PatternLeaderboardEntry]:
    rows = (
        db.query(PatternPerformance)
        .filter(PatternPerformance.sample_size > 0)
        .order_by(PatternPerformance.expectancy.desc().nulls_last())
        .limit(limit)
        .all()
    )
    return [
        PatternLeaderboardEntry(
            pattern_type=r.pattern_type, regime=r.regime, sample_size=r.sample_size,
            win_rate=r.win_rate, expectancy=r.expectancy,
        )
        for r in rows
    ]


def _regime_distribution(db: Session, window_days: int) -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(MarketRegime.regime, func.count(MarketRegime.id))
        .filter(MarketRegime.ts >= cutoff)
        .group_by(MarketRegime.regime)
        .all()
    )
    return {regime: count for regime, count in rows}


def build_analytics_overview(
    db: Session,
    *,
    equity_curve_limit: int = EQUITY_CURVE_LIMIT,
    tier_window_days: int = TIER_WINDOW_DAYS,
    regime_window_days: int = REGIME_WINDOW_DAYS,
    pattern_leaderboard_limit: int = PATTERN_LEADERBOARD_LIMIT,
) -> AnalyticsOverview:
    return AnalyticsOverview(
        equity_curve=_equity_curve(db, equity_curve_limit),
        trade_stats=_trade_stats(db),
        drawdown=_drawdown_stats(db),
        tier_distribution=_tier_distribution(db, tier_window_days),
        pattern_leaderboard=_pattern_leaderboard(db, pattern_leaderboard_limit),
        regime_distribution=_regime_distribution(db, regime_window_days),
    )
