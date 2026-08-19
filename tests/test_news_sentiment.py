from datetime import datetime, timedelta, timezone

from packages.quant.news.sentiment import (
    BEARISH,
    BULLISH,
    UNKNOWN,
    VERY_BEARISH,
    VERY_BULLISH,
    classify_sentiment,
    compute_sentiment_shift,
)
from packages.shared.models import Asset, NewsEvent, NewsImpact

NOW = datetime.now(timezone.utc)


def test_bullish_headline_classifies_bullish():
    result = classify_sentiment("Company reports record profit, shares surge on strong guidance")
    assert result.sentiment in (BULLISH, VERY_BULLISH)
    assert result.confidence > 0


def test_bearish_headline_classifies_bearish():
    result = classify_sentiment("Central bank surprise triggers market crash, shares plunge")
    assert result.sentiment in (BEARISH, VERY_BEARISH)


def test_no_sentiment_words_is_unknown_not_forced_neutral():
    result = classify_sentiment("Central bank holds policy rate steady")
    assert result.sentiment == UNKNOWN
    assert result.confidence == 0.0


def test_sentiment_is_never_treated_as_direction_by_the_function_itself():
    # Prompt 6 §11: sentiment is a tone read, never a price-direction claim.
    # This module has no "direction" output at all -- only sentiment/confidence.
    result = classify_sentiment("Company beats earnings estimates handily")
    assert not hasattr(result, "direction")
    assert not hasattr(result, "price_direction")


def _seed_news_impact(db_session, asset_id: int, sentiment: str, hours_ago: float) -> None:
    event = NewsEvent(
        source="Reuters", published_at=NOW - timedelta(hours=hours_ago), headline=f"Headline {hours_ago}",
        category="other", sentiment=sentiment,
    )
    db_session.add(event)
    db_session.commit()
    db_session.add(NewsImpact(
        news_event_id=event.id, asset_id=asset_id, impact="medium", direction="bullish" if sentiment.startswith("bull") or sentiment == "very_bullish" else "bearish",
        confidence=0.6, horizon_hours=12, rationale="test",
    ))
    db_session.commit()


def test_sentiment_shift_detects_a_swing_to_bearish(db_session):
    asset = Asset(symbol="SHIFTTEST1", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    # Baseline (last 24h): mostly bullish.
    for _ in range(4):
        _seed_news_impact(db_session, asset.id, "bullish", hours_ago=20.0)
    # Recent (last 2h): all bearish.
    for _ in range(3):
        _seed_news_impact(db_session, asset.id, "bearish", hours_ago=0.5)

    shift = compute_sentiment_shift(db_session, asset.id)
    assert shift.detected is True
    assert shift.shift is not None and shift.shift < 0


def test_sentiment_shift_not_detected_with_insufficient_samples(db_session):
    asset = Asset(symbol="SHIFTTEST2", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    _seed_news_impact(db_session, asset.id, "bearish", hours_ago=0.5)  # only 1 recent sample

    shift = compute_sentiment_shift(db_session, asset.id)
    assert shift.detected is False


def test_sentiment_shift_no_news_returns_no_data(db_session):
    asset = Asset(symbol="SHIFTTEST3", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    shift = compute_sentiment_shift(db_session, asset.id)
    assert shift.recent_bullish_share is None
    assert shift.detected is False
