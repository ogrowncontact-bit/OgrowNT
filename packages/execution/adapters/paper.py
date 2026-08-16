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
from packages.execution.fills import SPREAD_BPS, simulate_fill
from packages.shared.market_data import get_latest_candle_row


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

        fill = simulate_fill(mid_price=candle.close, volume=candle.volume, qty=order.qty, side=order.side)

        return OrderResult(
            broker_order_id=str(uuid4()),
            status="filled",
            filled_price=fill.price,
            filled_at=datetime.now(timezone.utc),
            fees=fill.fees,
            slippage_bps=fill.slippage_bps,
            detail={"mid_price": candle.close, "spread_bps": SPREAD_BPS},
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
