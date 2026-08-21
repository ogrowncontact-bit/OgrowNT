"""packages/execution/quality.py -- "PROMPT 13" §43-45."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.execution.quality import assess_execution_quality
from packages.shared.models import Execution, Order


def test_no_orders_is_honestly_not_evaluated(db_session):
    result = assess_execution_quality(db_session)
    assert result.evaluated is False
    assert result.fill_ratio is None


def test_fully_filled_orders_have_fill_ratio_one(db_session):
    db_session.add_all([
        Order(order_type="market", side="buy", qty=1.0, status="filled", filled_price=100.0, expected_price=100.0, latency_ms=5.0, slippage_bps=2.0),
        Order(order_type="market", side="buy", qty=1.0, status="filled", filled_price=101.0, expected_price=100.0, latency_ms=7.0, slippage_bps=3.0),
    ])
    db_session.commit()

    result = assess_execution_quality(db_session)
    assert result.evaluated is True
    assert result.fill_ratio == 1.0
    assert result.avg_latency_ms == 6.0
    assert result.avg_slippage_bps == 2.5


def test_rejected_orders_count_toward_rejected_but_not_fill_ratio_average(db_session):
    order = Order(order_type="market", side="buy", qty=1.0, status="rejected")
    db_session.add(order)
    db_session.commit()

    result = assess_execution_quality(db_session)
    assert result.rejected_orders == 1
    assert result.fill_ratio == 0.0  # a rejection is a genuine 0% fill, included in the average


def test_partial_fill_ratio_uses_the_execution_row_when_present(db_session):
    order = Order(order_type="market", side="buy", qty=10.0, status="partially_filled", filled_price=100.0)
    db_session.add(order)
    db_session.commit()
    db_session.add(Execution(order_id=order.id, symbol="X", side="buy", quantity=3.0, price=100.0, fee=0.1, ts=datetime.now(timezone.utc)))
    db_session.commit()

    result = assess_execution_quality(db_session)
    assert result.fill_ratio == 0.3


def test_price_deviation_uses_expected_vs_filled_price(db_session):
    db_session.add(Order(order_type="market", side="buy", qty=1.0, status="filled", filled_price=110.0, expected_price=100.0))
    db_session.commit()

    result = assess_execution_quality(db_session)
    assert result.avg_price_deviation_pct == 10.0
