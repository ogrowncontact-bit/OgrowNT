from datetime import datetime, timedelta, timezone

from packages.quant.learning.memory import find_similar_contexts, similar_context_win_rate
from packages.shared.models import Asset, MarketMemory, Signal, StrategyRow


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _memory(db_session, asset, *, regime, pattern_type, direction, outcome, minutes_ago=0):
    row = MarketMemory(
        ts=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago), asset_id=asset.id,
        context={"regime": regime, "pattern_type": pattern_type, "direction": direction}, outcome=outcome,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_matches_are_ranked_by_number_of_matching_fields(db_session):
    asset = _asset(db_session, "MEMRANK")
    _memory(db_session, asset, regime="trending_bull", pattern_type="momentum", direction="long", outcome="win", minutes_ago=10)
    _memory(db_session, asset, regime="trending_bull", pattern_type="breakout", direction="short", outcome="loss", minutes_ago=5)

    results = find_similar_contexts(db_session, regime="trending_bull", pattern_type="momentum", direction="long", k=10)
    assert len(results) == 2
    assert results[0].context["pattern_type"] == "momentum"  # 3-field match ranks above 1-field match


def test_unresolved_outcomes_are_excluded(db_session):
    asset = _asset(db_session, "MEMUNRESOLVED")
    row = MarketMemory(ts=datetime.now(timezone.utc), asset_id=asset.id, context={"regime": "ranging", "pattern_type": None, "direction": "long"}, outcome=None)
    db_session.add(row)
    db_session.commit()

    results = find_similar_contexts(db_session, regime="ranging", pattern_type=None, direction="long", k=10)
    assert results == []


def test_no_matching_field_excludes_row(db_session):
    asset = _asset(db_session, "MEMNOMATCH")
    _memory(db_session, asset, regime="ranging", pattern_type="reversal", direction="short", outcome="loss")

    results = find_similar_contexts(db_session, regime="trending_bull", pattern_type="momentum", direction="long", k=10)
    assert results == []


def test_exclude_signal_id_omits_self(db_session):
    asset = _asset(db_session, "MEMSELF")
    strategy = StrategyRow(code="memself_v1", name="memself_v1", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0, status="executed")
    db_session.add(signal)
    db_session.commit()

    row = MarketMemory(ts=datetime.now(timezone.utc), asset_id=asset.id, signal_id=signal.id, context={"regime": "ranging", "pattern_type": None, "direction": "long"}, outcome="win")
    db_session.add(row)
    db_session.commit()

    results = find_similar_contexts(db_session, regime="ranging", pattern_type=None, direction="long", k=10, exclude_signal_id=signal.id)
    assert results == []


def test_similar_context_win_rate_computes_ratio():
    class _Row:
        def __init__(self, outcome):
            self.outcome = outcome

    rows = [_Row("win"), _Row("win"), _Row("loss"), _Row(None)]
    assert similar_context_win_rate(rows) == round(2 / 3, 4)


def test_similar_context_win_rate_none_when_no_resolved_rows():
    class _Row:
        def __init__(self, outcome):
            self.outcome = outcome

    assert similar_context_win_rate([_Row(None)]) is None
