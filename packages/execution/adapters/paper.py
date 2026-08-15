"""PaperExecutionProvider — the only ExecutionProvider enabled by default
(docs/blueprint/04-agents-architecture.md#agent-11). Simulates a market
order fill against the latest known price: half the configured spread
against the trader, plus slippage that grows with order size relative to
the asset's recent volume, plus a flat fee rate. Never sends anything to a
real broker/exchange — there is no network call in this file.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from packages.execution.adapters.base import BalanceSnapshot, OrderRequest, OrderResult
from packages.shared.market_data import get_latest_candle_row

SPREAD_BPS = 5.0
FEE_RATE = 0.0005
BASE_SLIPPAGE_BPS = 2.0
MAX_VOLUME_RATIO_FOR_SLIPPAGE = 5.0


class PaperExecutionProvider:
    name = "paper"
    is_paper = True

    def __init__(self, db: Session):
        self.db = db

    def submit_order(self, order: OrderRequest) -> OrderResult:
        candle = get_latest_candle_row(self.db, order.asset_id)
        if candle is None or candle.data_quality != "high":
            return OrderResult(
                broker_order_id=str(uuid4()), status="rejected", detail={"reason": "data_unavailable"}
            )

        mid_price = candle.close
        volume_ratio = (order.qty / candle.volume) if candle.volume else 1.0
        slippage_bps = BASE_SLIPPAGE_BPS * (1 + min(MAX_VOLUME_RATIO_FOR_SLIPPAGE, volume_ratio))
        half_spread = mid_price * (SPREAD_BPS / 10_000) / 2
        slippage = mid_price * (slippage_bps / 10_000)

        # Costs always work against the trader, regardless of side.
        fill_price = mid_price + half_spread + slippage if order.side == "buy" else mid_price - half_spread - slippage
        fees = fill_price * order.qty * FEE_RATE

        return OrderResult(
            broker_order_id=str(uuid4()),
            status="filled",
            filled_price=round(fill_price, 8),
            filled_at=datetime.now(timezone.utc),
            fees=round(fees, 4),
            slippage_bps=round(slippage_bps, 2),
            detail={"mid_price": mid_price, "spread_bps": SPREAD_BPS},
        )

    def cancel_order(self, broker_order_id: str) -> None:
        # Market orders fill synchronously in paper mode — nothing pending to cancel.
        return None

    def get_order(self, broker_order_id: str) -> OrderResult | None:
        # The paper provider is stateless between calls; order_manager.py
        # persists the authoritative record to the `orders` table.
        return None

    def get_balance(self) -> BalanceSnapshot:
        from packages.portfolio.state import compute_state

        state = compute_state(self.db)
        return BalanceSnapshot(cash=state.cash, equity=state.equity)
