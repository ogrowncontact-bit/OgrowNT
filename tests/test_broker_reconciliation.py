"""packages/execution/broker_reconciliation.py -- "PROMPT 13" §33-38, §78."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.execution.broker.base import AccountInfo, PositionInfo
from packages.execution.broker.paper import PaperBrokerAdapter
from packages.execution.broker.registry import get_or_create_broker_row
from packages.execution.broker_reconciliation import run_broker_reconciliation, run_broker_reconciliation_and_enforce
from packages.portfolio.state import compute_state
from packages.shared.models import (
    OHLCV,
    AccountSnapshot,
    Alert,
    Asset,
    BrokerPositionSnapshot,
    Position,
    ReconciliationRun,
    StrategyRow,
    SystemState,
)


class _StubBroker:
    def __init__(self, *, account: AccountInfo, positions: list[PositionInfo], open_orders: list | None = None):
        self.name = "stub"
        self._account = account
        self._positions = positions
        self._open_orders = open_orders or []

    def get_account(self) -> AccountInfo:
        return self._account

    def get_positions(self) -> list[PositionInfo]:
        return self._positions

    def get_open_orders(self) -> list:
        return self._open_orders


def _asset(db_session, symbol: str, price: float) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price, low=price, close=price, volume=1000))
    db_session.commit()
    return asset


def test_paper_adapter_reconciles_clean_by_construction(db_session):
    """PaperBrokerAdapter's own view is derived from the same internal
    tables it's compared against -- see the module's own docstring for why
    this is honest, not a tautology worth hiding."""
    adapter = PaperBrokerAdapter(db_session)
    result = run_broker_reconciliation(db_session, adapter)
    assert result.ok is True
    assert result.violations == []


def test_balance_mismatch_is_detected(db_session):
    internal = compute_state(db_session)
    stub = _StubBroker(account=AccountInfo(
        balance=internal.cash, available_balance=internal.cash, equity=internal.equity + 100_000.0,
        margin=0.0, margin_used=0.0, margin_available=internal.cash, currency="USD", ts=datetime.now(timezone.utc),
    ), positions=[])
    result = run_broker_reconciliation(db_session, stub)
    assert result.ok is False
    assert any("balance_mismatch" in v for v in result.violations)


def test_missing_position_at_broker_is_detected(db_session):
    asset = _asset(db_session, "RECONMISSING", 100.0)
    strategy = StrategyRow(code="recon_missing_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    db_session.add(Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=1.0, status="open"))
    db_session.commit()

    internal = compute_state(db_session)
    stub = _StubBroker(account=AccountInfo(
        balance=internal.cash, available_balance=internal.cash, equity=internal.equity,
        margin=0.0, margin_used=0.0, margin_available=internal.cash, currency="USD", ts=datetime.now(timezone.utc),
    ), positions=[])  # the broker reports NOTHING despite an internally-open position
    result = run_broker_reconciliation(db_session, stub)
    assert result.ok is False
    assert any("missing_at_broker: RECONMISSING" in v for v in result.position_mismatches)


def test_unexpected_position_at_broker_is_detected(db_session):
    internal = compute_state(db_session)
    stub = _StubBroker(account=AccountInfo(
        balance=internal.cash, available_balance=internal.cash, equity=internal.equity,
        margin=0.0, margin_used=0.0, margin_available=internal.cash, currency="USD", ts=datetime.now(timezone.utc),
    ), positions=[PositionInfo(symbol="GHOSTPOSITION", quantity=1.0, average_price=100.0, mark_price=100.0, unrealized_pnl=0.0, realized_pnl=None, side="long", leverage=1.0, margin=0.0)])
    result = run_broker_reconciliation(db_session, stub)
    assert result.ok is False
    assert any("unexpected_at_broker: GHOSTPOSITION" in v for v in result.position_mismatches)


def test_quantity_mismatch_is_detected(db_session):
    asset = _asset(db_session, "RECONQTY", 100.0)
    strategy = StrategyRow(code="recon_qty_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    db_session.add(Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=1.0, status="open"))
    db_session.commit()

    internal = compute_state(db_session)
    stub = _StubBroker(account=AccountInfo(
        balance=internal.cash, available_balance=internal.cash, equity=internal.equity,
        margin=0.0, margin_used=0.0, margin_available=internal.cash, currency="USD", ts=datetime.now(timezone.utc),
    ), positions=[PositionInfo(symbol="RECONQTY", quantity=999.0, average_price=100.0, mark_price=100.0, unrealized_pnl=0.0, realized_pnl=None, side="long", leverage=1.0, margin=0.0)])
    result = run_broker_reconciliation(db_session, stub)
    assert result.ok is False
    assert any("quantity_mismatch" in v for v in result.position_mismatches)


def test_and_enforce_persists_snapshots_and_reconciliation_run(db_session):
    adapter = PaperBrokerAdapter(db_session)
    broker_row = get_or_create_broker_row(db_session, name="paper", kind="paper")
    db_session.commit()

    result = run_broker_reconciliation_and_enforce(db_session, adapter, broker_id=broker_row.id)
    assert result.ok is True
    assert db_session.query(ReconciliationRun).filter(ReconciliationRun.broker_id == broker_row.id).count() == 1
    assert db_session.query(AccountSnapshot).filter(AccountSnapshot.broker_id == broker_row.id).count() == 1


def test_and_enforce_pauses_trading_on_mismatch_idempotently(db_session):
    broker_row = get_or_create_broker_row(db_session, name="stub", kind="paper")
    db_session.commit()
    internal = compute_state(db_session)
    stub = _StubBroker(account=AccountInfo(
        balance=internal.cash, available_balance=internal.cash, equity=internal.equity + 100_000.0,
        margin=0.0, margin_used=0.0, margin_available=internal.cash, currency="USD", ts=datetime.now(timezone.utc),
    ), positions=[])

    first = run_broker_reconciliation_and_enforce(db_session, stub, broker_id=broker_row.id)
    assert first.ok is False
    state = db_session.get(SystemState, True)
    assert state.trading_paused is True
    first_alert_count = db_session.query(Alert).count()

    second = run_broker_reconciliation_and_enforce(db_session, stub, broker_id=broker_row.id)
    assert second.ok is False
    # Same "page once, not every tick" discipline as the existing cash-only
    # reconciliation -- a second consecutive failure doesn't re-alert.
    assert db_session.query(Alert).count() == first_alert_count


def test_broker_position_snapshot_rows_are_created(db_session):
    asset = _asset(db_session, "RECONSNAPSHOT", 100.0)
    strategy = StrategyRow(code="recon_snapshot_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    db_session.add(Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=1.0, status="open"))
    db_session.commit()

    adapter = PaperBrokerAdapter(db_session)
    broker_row = get_or_create_broker_row(db_session, name="paper", kind="paper")
    db_session.commit()
    run_broker_reconciliation_and_enforce(db_session, adapter, broker_id=broker_row.id)

    snapshots = db_session.query(BrokerPositionSnapshot).filter(BrokerPositionSnapshot.broker_id == broker_row.id).all()
    assert len(snapshots) == 1
    assert snapshots[0].symbol == "RECONSNAPSHOT"
