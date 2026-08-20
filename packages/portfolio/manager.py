"""Portfolio Manager — "PROMPT 8" §12-17.

Formalizes one check the Risk Engine's own portfolio-exposure gate
(packages/risk/engine.py's steps 4-7) does NOT already make: how much of
the book's capital is allocated to a single *strategy*, as opposed to a
single *asset* (max_single_asset_pct) or a correlated *cluster* of assets
(max_correlated_cluster_pct). A strategy with a real edge can still
concentrate the whole account's risk if it's allowed to open positions
across every asset it's ever profitable on, at the same time, uncapped —
the existing per-asset and correlation-cluster checks don't catch that,
since they group by asset/correlation, never by strategy.

Deliberately thin, not a second Risk Engine: this makes exactly one
additional decision (AllocationDecision), consulted after Risk Engine
approval and before Execution, matching the spec's approval gate (§13:
"Opportunity VALIDATED AND Risk APPROVED AND Portfolio APPROVED AND
TradingMode PAPER"). Every other portfolio-level number (exposure,
correlation, headroom, equity) is already computed once in
packages/risk/engine.py and packages/portfolio/state.py; duplicating that
math here would create two sources of truth for the same number — the one
thing this codebase has consistently avoided (see e.g.
packages/backtest/reality_gap.py's docstring on the same principle).
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.portfolio.state import PortfolioState
from packages.risk.config import RiskLimits


@dataclass(frozen=True)
class AllocationDecision:
    approved: bool
    reason: str
    strategy_allocation_pct: float  # this strategy's existing exposure, as % of equity, before this candidate
    strategy_headroom_pct: float  # 0.0 when approved=False
    approved_notional_pct: float  # candidate_notional_pct, capped to headroom when it didn't fully fit


def evaluate_allocation(
    *,
    strategy_id: int,
    candidate_notional_pct: float,
    portfolio_state: PortfolioState,
    limits: RiskLimits,
) -> AllocationDecision:
    """candidate_notional_pct is the position Risk Engine already sized,
    expressed as % of equity — this only ever caps it further, never raises
    it (mirrors packages/risk/position_sizing.py's "smallest of every
    applicable cap" rule, just for one more cap Risk Engine doesn't know
    about)."""
    equity = portfolio_state.equity
    if equity <= 0 or candidate_notional_pct <= 0:
        return AllocationDecision(False, "invalid_input", 0.0, 0.0, 0.0)

    existing_strategy_notional = sum(
        p.entry_price * p.size for p in portfolio_state.open_positions if p.strategy_id == strategy_id
    )
    existing_strategy_pct = round((existing_strategy_notional / equity) * 100, 4)
    headroom_pct = round(limits.portfolio.max_strategy_allocation_pct - existing_strategy_pct, 4)

    if headroom_pct <= 0:
        return AllocationDecision(False, "strategy_allocation_exceeded", existing_strategy_pct, 0.0, 0.0)

    approved_pct = min(candidate_notional_pct, headroom_pct)
    reason = "approved" if approved_pct >= candidate_notional_pct else "approved_capped"
    return AllocationDecision(True, reason, existing_strategy_pct, headroom_pct, approved_pct)
