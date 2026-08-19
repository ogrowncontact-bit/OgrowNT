from datetime import datetime, timedelta, timezone

from packages.risk.config import load_risk_limits
from packages.risk.news_guard import CRITICAL, ELEVATED, HIGH, NORMAL, evaluate_news_risk
from packages.shared.models import MacroEvent, NewsEvent

LIMITS = load_risk_limits()
NOW = datetime.now(timezone.utc)


def _macro(db_session, *, importance: str, minutes_out: float) -> MacroEvent:
    event = MacroEvent(
        event="Test Macro Event", country="US", currency="USD",
        scheduled_at=NOW + timedelta(minutes=minutes_out), importance=importance,
        forecast=1.0, previous=1.0, status="scheduled",
    )
    db_session.add(event)
    db_session.commit()
    return event


def _news(db_session, *, importance: str, minutes_ago: float) -> NewsEvent:
    event = NewsEvent(
        source="Reuters", published_at=NOW - timedelta(minutes=minutes_ago),
        headline="Test breaking headline", category="other", importance=importance,
    )
    db_session.add(event)
    db_session.commit()
    return event


def test_normal_when_no_events(db_session):
    verdict = evaluate_news_risk(db_session, LIMITS, now=NOW)
    assert verdict.level == NORMAL
    assert not verdict.blocked
    assert verdict.size_multiplier == 1.0


def test_critical_macro_event_imminent_blocks(db_session):
    _macro(db_session, importance="critical", minutes_out=10)
    verdict = evaluate_news_risk(db_session, LIMITS, now=NOW)
    assert verdict.level == CRITICAL
    assert verdict.blocked
    assert verdict.size_multiplier == 0.0
    assert any("macro_event_imminent" in r for r in verdict.reasons)


def test_critical_recent_news_blocks(db_session):
    _news(db_session, importance="critical", minutes_ago=5)
    verdict = evaluate_news_risk(db_session, LIMITS, now=NOW)
    assert verdict.level == CRITICAL
    assert verdict.blocked


def test_high_macro_event_imminent_reduces_not_blocks(db_session):
    _macro(db_session, importance="high", minutes_out=10)
    verdict = evaluate_news_risk(db_session, LIMITS, now=NOW)
    assert verdict.level == HIGH
    assert not verdict.blocked
    assert 0.0 < verdict.size_multiplier < 1.0


def test_high_macro_event_far_out_is_only_elevated(db_session):
    # Within the wider elevated window but not the tight pre-event window.
    _macro(db_session, importance="high", minutes_out=80)
    verdict = evaluate_news_risk(db_session, LIMITS, now=NOW)
    assert verdict.level == ELEVATED
    assert not verdict.blocked


def test_macro_event_far_in_future_is_normal(db_session):
    _macro(db_session, importance="critical", minutes_out=24 * 60)
    verdict = evaluate_news_risk(db_session, LIMITS, now=NOW)
    assert verdict.level == NORMAL


def test_low_importance_news_does_not_escalate(db_session):
    _news(db_session, importance="low", minutes_ago=5)
    verdict = evaluate_news_risk(db_session, LIMITS, now=NOW)
    assert verdict.level == NORMAL
