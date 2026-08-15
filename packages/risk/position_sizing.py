"""Position Sizing — docs/blueprint/08-risk-engine.md#position-sizing.

Always applies the SMALLEST of: strategy/risk-budget sizing, the portfolio
exposure headroom, the correlation-cluster headroom, and the single-asset
cap. Never a fixed size regardless of context.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.risk.config import RiskLimits

MIN_VOLATILITY_FACTOR = 1.0  # never divides the size UP, only down


@dataclass(frozen=True)
class SizingResult:
    quantity: float
    notional: float
    binding_constraint: str
    detail: dict


def calculate_position_size(
    *,
    capital: float,
    entry_price: float,
    stop_price: float,
    confidence: float,
    volatility_factor: float,
    portfolio_headroom_pct: float,
    correlation_headroom_pct: float,
    limits: RiskLimits,
) -> SizingResult:
    stop_distance_pct = abs(entry_price - stop_price) / entry_price if entry_price else 0.0
    if stop_distance_pct <= 0 or capital <= 0:
        return SizingResult(quantity=0.0, notional=0.0, binding_constraint="invalid_input", detail={})

    risk_budget = capital * (limits.per_trade.max_risk_pct / 100)
    raw_notional = risk_budget / stop_distance_pct

    confidence_clamped = min(1.0, max(0.0, confidence))
    confidence_adj_notional = raw_notional * confidence_clamped

    vol_factor = max(MIN_VOLATILITY_FACTOR, volatility_factor)
    vol_adj_notional = confidence_adj_notional / vol_factor

    caps = {
        "risk_budget": vol_adj_notional,
        "portfolio_headroom": capital * (max(0.0, portfolio_headroom_pct) / 100),
        "correlation_headroom": capital * (max(0.0, correlation_headroom_pct) / 100),
        "single_asset_cap": capital * (limits.portfolio.max_single_asset_pct / 100),
    }
    binding_constraint = min(caps, key=lambda k: caps[k])
    final_notional = max(0.0, caps[binding_constraint])

    return SizingResult(
        quantity=final_notional / entry_price,
        notional=final_notional,
        binding_constraint=binding_constraint,
        detail={"stop_distance_pct": stop_distance_pct, "risk_budget": risk_budget, **caps},
    )
