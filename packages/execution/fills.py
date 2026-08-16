"""Pure fill-simulation math, shared by PaperExecutionProvider
(packages/execution/adapters/paper.py) and the Backtest Engine
(packages/backtest/engine.py) so a backtest's costs are never a
second, drifting copy of production's fee/slippage model
(docs/blueprint/10-backtesting-paper-trading.md: "usa o mesmo Risk
Engine/PositionSizer... fees, slippage model" as production).
"""
from __future__ import annotations

from dataclasses import dataclass

SPREAD_BPS = 5.0
FEE_RATE = 0.0005
BASE_SLIPPAGE_BPS = 2.0
MAX_VOLUME_RATIO_FOR_SLIPPAGE = 5.0


@dataclass(frozen=True)
class SimulatedFill:
    price: float
    fees: float
    slippage_bps: float


def simulate_fill(*, mid_price: float, volume: float, qty: float, side: str) -> SimulatedFill:
    """Half the configured spread against the trader, plus slippage that
    grows with order size relative to the bar's volume, plus a flat fee
    rate — costs always work against the trader, regardless of side."""
    volume_ratio = (qty / volume) if volume else 1.0
    slippage_bps = BASE_SLIPPAGE_BPS * (1 + min(MAX_VOLUME_RATIO_FOR_SLIPPAGE, volume_ratio))
    half_spread = mid_price * (SPREAD_BPS / 10_000) / 2
    slippage = mid_price * (slippage_bps / 10_000)

    fill_price = mid_price + half_spread + slippage if side == "buy" else mid_price - half_spread - slippage
    fees = fill_price * qty * FEE_RATE

    return SimulatedFill(price=round(fill_price, 8), fees=round(fees, 4), slippage_bps=round(slippage_bps, 2))
