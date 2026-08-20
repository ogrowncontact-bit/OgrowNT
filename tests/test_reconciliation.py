"""packages/portfolio/reconciliation.py — "PROMPT 8" §69-71."""
from datetime import datetime, timezone

from packages.execution.adapters.paper import PaperExecutionProvider
from packages.execution.order_manager import close_position, open_position
from packages.portfolio.reconciliation import reconcile_and_enforce, run_reconciliation
from packages.shared.models import OHLCV, Alert, Asset, Order, Position, Signal, StrategyRow, SystemState, TradingEvent
from packages.shared.settings import get_settings


def _asset_with_price(db_session, symbol: str, price: float) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1000)
    )
    db_session.commit()
    return asset


def test_a_fresh_account_with_no_activity_reconciles_clean(db_session):
    result = run_reconciliation(db_session)
    assert result.ok
    assert result.actual_cash == get_settings().initial_paper_capital
    assert result.expected_cash == get_settings().initial_paper_capital


def test_a_real_open_and_close_cycle_never_desyncs_the_ledger(db_session):
    """The most important case: the SAME functions that maintain the
    incremental ledger (packages/execution/order_manager.py) must always
    agree with reconciliation's from-scratch reconstruction."""
    asset = _asset_with_price(db_session, "RECONCILECYCLE", 100.0)
    strategy = StrategyRow(code="reconcile_strategy", name="Reconcile", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="approved",
    )
    db_session.add(signal)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    position = open_position(db_session, provider, signal=signal, asset=asset, quantity=1.0)
    assert position is not None
    assert run_reconciliation(db_session).ok  # still clean with one open position

    close_position(db_session, provider, position, asset=asset, exit_reason="manual_close")
    result = run_reconciliation(db_session)
    assert result.ok, result.violations


def test_reconcile_and_enforce_pauses_trading_on_a_cash_mismatch(db_session):
    from packages.portfolio.state import refresh_snapshot

    # Deliberately desync the ledger from reality: write a snapshot whose
    # cash doesn't match "initial capital, no activity".
    refresh_snapshot(db_session, cash=get_settings().initial_paper_capital - 500.0)

    result = reconcile_and_enforce(db_session)
    assert not result.ok
    assert any("cash_mismatch" in v for v in result.violations)

    state = db_session.get(SystemState, True)
    assert state.trading_paused
    assert "reconciliation_mismatch" in state.paused_reason

    assert db_session.query(TradingEvent).filter(TradingEvent.event_type == "reconciliation_mismatch").count() == 1
    assert db_session.query(Alert).filter(Alert.category == "system", Alert.severity == "critical").count() == 1


def test_reconcile_and_enforce_does_not_double_alert_when_already_paused(db_session):
    from packages.portfolio.state import refresh_snapshot

    refresh_snapshot(db_session, cash=get_settings().initial_paper_capital - 500.0)
    reconcile_and_enforce(db_session)
    reconcile_and_enforce(db_session)  # a second consecutive failed check

    assert db_session.query(Alert).filter(Alert.category == "system", Alert.severity == "critical").count() == 1
    # Both mismatches are still logged as events -- only the pause+alert is deduplicated.
    assert db_session.query(TradingEvent).filter(TradingEvent.event_type == "reconciliation_mismatch").count() == 2


def test_negative_position_size_is_flagged(db_session):
    asset = _asset_with_price(db_session, "RECONCILENEGSIZE", 100.0)
    strategy = StrategyRow(code="reconcile_negsize_strategy", name="Neg Size", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    db_session.add(
        Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=-1.0, status="open")
    )
    db_session.commit()

    result = run_reconciliation(db_session)
    assert not result.ok
    assert any("non_positive_position_size" in v for v in result.violations)


def test_negative_fees_are_flagged(db_session):
    db_session.add(Order(order_type="market", side="buy", qty=1.0, status="filled", fees=-1.0))
    db_session.commit()

    result = run_reconciliation(db_session)
    assert not result.ok
    assert any("negative_fees" in v for v in result.violations)
