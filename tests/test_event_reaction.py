from datetime import datetime, timedelta, timezone

from packages.quant.news.event_reaction import MIN_SAMPLES_FOR_REACTION, compute_event_reactions
from packages.shared.models import OHLCV, Asset, EventReaction, NewsEvent, NewsImpact

NOW = datetime.now(timezone.utc)
HORIZON_HOURS = 4.0


def _seed_reaction_observation(db_session, asset_id: int, *, published_hours_ago: float, pct_move: float) -> None:
    published_at = NOW - timedelta(hours=published_hours_ago)
    db_session.add(OHLCV(asset_id=asset_id, timeframe="1m", ts=published_at, open=100.0, high=100.5, low=99.5, close=100.0, volume=100))
    db_session.add(OHLCV(
        asset_id=asset_id, timeframe="1m", ts=published_at + timedelta(hours=HORIZON_HOURS),
        open=100.0, high=101.0, low=99.0, close=100.0 * (1 + pct_move / 100), volume=100,
    ))
    db_session.commit()

    event = NewsEvent(source="Reuters", published_at=published_at, headline=f"Event {published_hours_ago}", category="inflation")
    db_session.add(event)
    db_session.commit()
    db_session.add(NewsImpact(
        news_event_id=event.id, asset_id=asset_id, impact="high", direction="bearish",
        confidence=0.7, horizon_hours=HORIZON_HOURS, rationale="test",
    ))
    db_session.commit()


def test_below_minimum_sample_produces_no_row(db_session):
    asset = Asset(symbol="REACTMIN", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    for i in range(MIN_SAMPLES_FOR_REACTION - 1):
        _seed_reaction_observation(db_session, asset.id, published_hours_ago=20 + i * 10, pct_move=-1.0)

    compute_event_reactions(db_session, horizon_hours=HORIZON_HOURS)
    row = db_session.query(EventReaction).filter(EventReaction.asset_id == asset.id).first()
    assert row is None


def test_meeting_minimum_sample_produces_a_real_confidence_gated_row(db_session):
    asset = Asset(symbol="REACTOK", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    # Spaced well beyond HORIZON_HOURS so no observation's "after" candle
    # collides with another's "before" candle on the OHLCV primary key.
    for i in range(MIN_SAMPLES_FOR_REACTION):
        _seed_reaction_observation(db_session, asset.id, published_hours_ago=20 + i * 10, pct_move=-1.0)

    compute_event_reactions(db_session, horizon_hours=HORIZON_HOURS)
    row = db_session.query(EventReaction).filter(EventReaction.asset_id == asset.id, EventReaction.event_category == "inflation").first()
    assert row is not None
    assert row.sample_size == MIN_SAMPLES_FOR_REACTION
    assert row.avg_reaction_pct < 0  # every observation moved down -1%
    assert row.positive_rate == 0.0
    assert row.confidence is not None and row.confidence > 0


def test_events_still_in_the_horizon_window_are_not_counted_yet(db_session):
    asset = Asset(symbol="REACTPENDING", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    # Published recently enough that horizon_hours hasn't elapsed -- no
    # "after" candle exists yet, so this must not be silently guessed.
    for i in range(MIN_SAMPLES_FOR_REACTION):
        _seed_reaction_observation(db_session, asset.id, published_hours_ago=0.5 + i * 0.01, pct_move=-1.0)
        # Remove the "after" candle to simulate it not having happened yet.
        db_session.query(OHLCV).filter(
            OHLCV.asset_id == asset.id, OHLCV.ts > NOW - timedelta(hours=0.5)
        ).delete()
        db_session.commit()

    compute_event_reactions(db_session, horizon_hours=HORIZON_HOURS)
    row = db_session.query(EventReaction).filter(EventReaction.asset_id == asset.id).first()
    assert row is None
