from datetime import datetime, timedelta, timezone

from apps.worker.macro_agent import run_macro_calendar_cycle
from packages.data.connectors.macro.base import MacroEventItem
from packages.shared.models import Alert, MacroEvent

NOW = datetime.now(timezone.utc)


class _FakeMacroProvider:
    name = "fake"

    def __init__(self, items: list[MacroEventItem]) -> None:
        self._items = items

    def is_connected(self) -> bool:
        return True

    def get_events(self, start, end) -> list[MacroEventItem]:
        return [i for i in self._items if start <= i.scheduled_at <= end]


def test_creates_new_macro_event_rows(db_session):
    provider = _FakeMacroProvider([
        MacroEventItem(
            event="Test CPI", country="US", currency="USD", scheduled_at=NOW + timedelta(days=1),
            importance="high", forecast=3.0, previous=2.9, actual=None,
        )
    ])
    summary = run_macro_calendar_cycle(db_session, provider)
    assert summary["created"] == 1

    row = db_session.query(MacroEvent).filter(MacroEvent.event == "Test CPI").first()
    assert row is not None
    assert row.status == "scheduled"
    assert row.surprise is None


def test_upsert_does_not_duplicate_on_repeated_ingestion(db_session):
    item = MacroEventItem(
        event="Test GDP", country="US", currency="USD", scheduled_at=NOW + timedelta(days=2),
        importance="medium", forecast=2.0, previous=1.8, actual=None,
    )
    provider = _FakeMacroProvider([item])
    run_macro_calendar_cycle(db_session, provider)
    summary = run_macro_calendar_cycle(db_session, provider)
    assert summary["created"] == 0
    assert summary["updated"] == 1

    rows = db_session.query(MacroEvent).filter(MacroEvent.event == "Test GDP").all()
    assert len(rows) == 1


def test_surprise_computed_only_once_actual_appears(db_session):
    scheduled_at = NOW - timedelta(minutes=5)
    provider_before = _FakeMacroProvider([
        MacroEventItem(
            event="Test NFP", country="US", currency="USD", scheduled_at=scheduled_at,
            importance="critical", forecast=180.0, previous=175.0, actual=None,
        )
    ])
    run_macro_calendar_cycle(db_session, provider_before)
    row = db_session.query(MacroEvent).filter(MacroEvent.event == "Test NFP").first()
    assert row.status == "scheduled"
    assert row.surprise is None

    provider_after = _FakeMacroProvider([
        MacroEventItem(
            event="Test NFP", country="US", currency="USD", scheduled_at=scheduled_at,
            importance="critical", forecast=180.0, previous=175.0, actual=220.0,
        )
    ])
    summary = run_macro_calendar_cycle(db_session, provider_after)
    assert summary["resolved"] == 1

    db_session.refresh(row)
    assert row.status == "released"
    assert row.surprise == 40.0


def test_macro_surprise_alert_written_on_resolution(db_session):
    scheduled_at = NOW - timedelta(minutes=5)
    provider_before = _FakeMacroProvider([
        MacroEventItem(
            event="Test Rate Decision", country="US", currency="USD", scheduled_at=scheduled_at,
            importance="critical", forecast=5.25, previous=5.25, actual=None,
        )
    ])
    run_macro_calendar_cycle(db_session, provider_before)

    provider_after = _FakeMacroProvider([
        MacroEventItem(
            event="Test Rate Decision", country="US", currency="USD", scheduled_at=scheduled_at,
            importance="critical", forecast=5.25, previous=5.25, actual=5.50,
        )
    ])
    run_macro_calendar_cycle(db_session, provider_after)

    alert = db_session.query(Alert).filter(Alert.category == "news").filter(
        Alert.message.like("%Macro surprise%Test Rate Decision%")
    ).first()
    assert alert is not None


def test_high_impact_event_alert_when_imminent(db_session):
    provider = _FakeMacroProvider([
        MacroEventItem(
            event="Test Imminent Critical Event", country="US", currency="USD",
            scheduled_at=NOW + timedelta(minutes=10), importance="critical",
            forecast=1.0, previous=1.0, actual=None,
        )
    ])
    run_macro_calendar_cycle(db_session, provider)
    alert = db_session.query(Alert).filter(Alert.category == "news").filter(
        Alert.message.like("%High-impact macro event upcoming%Test Imminent Critical Event%")
    ).first()
    assert alert is not None


def test_no_high_impact_alert_when_event_far_in_future(db_session):
    provider = _FakeMacroProvider([
        MacroEventItem(
            event="Test Far Future Event", country="US", currency="USD",
            scheduled_at=NOW + timedelta(days=10), importance="critical",
            forecast=1.0, previous=1.0, actual=None,
        )
    ])
    run_macro_calendar_cycle(db_session, provider)
    alert = db_session.query(Alert).filter(Alert.category == "news").filter(
        Alert.message.like("%Test Far Future Event%")
    ).first()
    assert alert is None
