from datetime import datetime, timezone

from apps.worker.trade_monitor import run_trade_monitor_cycle
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.llm.client import LLMClient
from packages.shared.models import OHLCV, Asset, Position, StrategyRow, Trade, TradeJournal


class _FakeLLMClient(LLMClient):
    def __init__(self, response):
        self._response = response

    def is_available(self):
        return True

    def complete_json(self, system_prompt, user_content, max_tokens=1024):
        return self._response


def _asset_with_price(db_session, symbol: str, price: float) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1000)
    )
    db_session.commit()
    return asset


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0", lifecycle_stage="paper")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def test_losing_trade_creates_journal_entry_without_llm_configured(db_session):
    asset = _asset_with_price(db_session, "JOURNALLOSS", 94.0)
    strategy = _strategy(db_session, "trend_following_v1_journal")
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, target_price=115.0, size=1.0, status="open")
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)  # no llm_client passed -> real LLMClient(), unavailable in test env

    trade = db_session.query(Trade).filter(Trade.position_id == position.id).first()
    journal = db_session.query(TradeJournal).filter(TradeJournal.trade_id == trade.id).first()
    assert journal is not None
    assert journal.expected_outcome == "win"
    assert journal.actual_outcome == "loss"
    assert journal.hypothesis is None
    assert journal.root_cause is None


def test_losing_trade_gets_llm_hypothesis_when_available(db_session):
    asset = _asset_with_price(db_session, "JOURNALLLM", 94.0)
    strategy = _strategy(db_session, "trend_following_v1_llmjournal")
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, target_price=115.0, size=1.0, status="open")
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    fake_client = _FakeLLMClient({"hypothesis": "Stop was too tight for realized volatility.", "root_cause": "normal_variance"})
    run_trade_monitor_cycle(db_session, provider, fake_client)

    trade = db_session.query(Trade).filter(Trade.position_id == position.id).first()
    journal = db_session.query(TradeJournal).filter(TradeJournal.trade_id == trade.id).first()
    assert journal.hypothesis == "Stop was too tight for realized volatility."
    assert journal.root_cause == "normal_variance"


def test_winning_trade_never_calls_llm_for_hypothesis(db_session):
    asset = _asset_with_price(db_session, "JOURNALWIN", 120.0)
    strategy = _strategy(db_session, "momentum_v1_journalwin")
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=90.0, target_price=115.0, size=1.0, status="open")
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)

    class _ExplodingClient(LLMClient):
        def __init__(self):
            pass

        def is_available(self):
            return True

        def complete_json(self, *a, **kw):
            raise AssertionError("must not be called for a trade that matched expectations")

    run_trade_monitor_cycle(db_session, provider, _ExplodingClient())

    trade = db_session.query(Trade).filter(Trade.position_id == position.id).first()
    journal = db_session.query(TradeJournal).filter(TradeJournal.trade_id == trade.id).first()
    assert journal.actual_outcome == "win"
    assert journal.hypothesis is None


def test_repeated_losses_recompute_strategy_performance_and_quarantine(db_session):
    strategy = _strategy(db_session, "breakout_v1_quarantine_test")
    provider = PaperExecutionProvider(db_session)

    for i in range(5):
        asset = _asset_with_price(db_session, f"QLOSS{i}", 94.0)
        position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, target_price=115.0, size=1.0, status="open")
        db_session.add(position)
        db_session.commit()
        run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(strategy)
    assert strategy.lifecycle_stage == "quarantine"

    from packages.shared.models import StrategyPerformance
    perf = (
        db_session.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy.id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )
    assert perf is not None
    assert perf.total_trades == 5
    assert perf.health_score is not None and perf.health_score < 35.0


def test_quarantined_strategy_stops_generating_new_signals(db_session):
    from apps.worker.strategy_runner import run_strategy_cycle

    strategy = _strategy(db_session, "trend_following_v1")  # matches a real ALL_STRATEGIES code
    strategy.lifecycle_stage = "quarantine"
    db_session.commit()

    asset = _asset_with_price(db_session, "QUARANTINEDRUN", 100.0)
    for i in range(60):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=100.0 + i * 0.1,
                high=100.5 + i * 0.1, low=99.5 + i * 0.1, close=100.0 + i * 0.1, volume=1000,
            )
        )
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    run_strategy_cycle(db_session, provider=provider)

    from packages.shared.models import Signal
    signals_for_strategy = db_session.query(Signal).filter(Signal.strategy_id == strategy.id).count()
    assert signals_for_strategy == 0
