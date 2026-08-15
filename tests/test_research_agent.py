from datetime import datetime, timedelta, timezone

from packages.llm.client import LLMClient
from packages.quant.learning.research import (
    MIN_SAMPLE_FOR_CANDIDATE,
    MIN_SAMPLE_FOR_VALIDATION,
    run_research_cycle,
)
from packages.shared.models import (
    Asset,
    LearnedRule,
    MarketRegime,
    Pattern,
    PatternPerformance,
    Position,
    Signal,
    StrategyPerformance,
    StrategyRow,
    Trade,
)


class _FakeLLMClient(LLMClient):
    def __init__(self, response):
        self._response = response

    def is_available(self):
        return True

    def complete_json(self, system_prompt, user_content, max_tokens=1024):
        return self._response


class _UnavailableLLMClient(LLMClient):
    def __init__(self):
        pass

    def is_available(self):
        return False


_VALID_PROPOSAL = {"condition": {"regime": "ranging"}, "conclusion": "Underperforms in this regime.", "confidence": 0.6}


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0", lifecycle_stage="paper")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _trades_for_strategy(db_session, strategy: StrategyRow, asset: Asset, r_multiples: list[float]) -> None:
    for i, r in enumerate(r_multiples):
        position = Position(
            asset_id=asset.id, strategy_id=strategy.id, direction="long",
            entry_price=100.0, current_stop=95.0, size=1.0, status="closed",
            realized_pnl=r * 10, exit_price=100 + r, exit_reason="target_hit",
        )
        db_session.add(position)
        db_session.commit()
        db_session.add(
            Trade(position_id=position.id, pnl=r * 10, r_multiple=r, outcome=("win" if r > 0 else "loss"), closed_at=datetime.now(timezone.utc) - timedelta(minutes=i))
        )
        db_session.commit()


def _trades_for_pattern(db_session, asset: Asset, strategy: StrategyRow, pattern_type: str, regime: str, r_multiples: list[float]) -> None:
    for i, r in enumerate(r_multiples):
        regime_row = MarketRegime(asset_id=asset.id, timeframe="1m", regime=regime, confidence=0.8, features={})
        db_session.add(regime_row)
        pattern_row = Pattern(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), pattern_type=pattern_type, pattern_class="technical", direction="bullish", strength=0.7, meta={})
        db_session.add(pattern_row)
        db_session.commit()

        signal = Signal(
            strategy_id=strategy.id, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0,
            regime_id=regime_row.id, pattern_id=pattern_row.id, status="executed",
        )
        db_session.add(signal)
        db_session.commit()

        position = Position(
            asset_id=asset.id, strategy_id=strategy.id, signal_id=signal.id, direction="long",
            entry_price=100.0, current_stop=95.0, size=1.0, status="closed",
            realized_pnl=r * 10, exit_price=100 + r, exit_reason="target_hit",
        )
        db_session.add(position)
        db_session.commit()
        db_session.add(
            Trade(position_id=position.id, pnl=r * 10, r_multiple=r, outcome=("win" if r > 0 else "loss"), closed_at=datetime.now(timezone.utc) - timedelta(minutes=i))
        )
        db_session.commit()


def test_healthy_pattern_never_proposed(db_session):
    db_session.add(PatternPerformance(pattern_type="momentum", regime="trending_bull", sample_size=MIN_SAMPLE_FOR_CANDIDATE, win_rate=0.7, avg_r_multiple=1.0, expectancy=1.0))
    db_session.commit()

    summary = run_research_cycle(db_session, _FakeLLMClient(_VALID_PROPOSAL))
    assert summary["proposed"] == 0


def test_thin_sample_never_proposed(db_session):
    db_session.add(PatternPerformance(pattern_type="reversal", regime="ranging", sample_size=MIN_SAMPLE_FOR_CANDIDATE - 1, win_rate=0.2, avg_r_multiple=-0.5, expectancy=-0.5))
    db_session.commit()

    summary = run_research_cycle(db_session, _FakeLLMClient(_VALID_PROPOSAL))
    assert summary["proposed"] == 0


def test_unhealthy_pattern_proposes_candidate_rule(db_session):
    db_session.add(PatternPerformance(pattern_type="breakout", regime="ranging", sample_size=MIN_SAMPLE_FOR_CANDIDATE, win_rate=0.2, avg_r_multiple=-0.5, expectancy=-0.5))
    db_session.commit()

    summary = run_research_cycle(db_session, _FakeLLMClient(_VALID_PROPOSAL))
    assert summary["proposed"] == 1

    rule = db_session.query(LearnedRule).filter(LearnedRule.scope == "pattern:breakout:ranging").first()
    assert rule is not None
    assert rule.status in ("candidate", "rejected")  # candidate immediately, then validation pass may reject (no raw trades -> stays candidate)
    assert rule.condition == {"regime": "ranging"}


def test_llm_unavailable_proposes_nothing(db_session):
    db_session.add(PatternPerformance(pattern_type="anomaly", regime="high_volatility", sample_size=MIN_SAMPLE_FOR_CANDIDATE, win_rate=0.1, avg_r_multiple=-1.0, expectancy=-1.0))
    db_session.commit()

    summary = run_research_cycle(db_session, _UnavailableLLMClient())
    assert summary["proposed"] == 0


def test_does_not_duplicate_existing_candidate_scope(db_session):
    db_session.add(PatternPerformance(pattern_type="volatility", regime="ranging", sample_size=MIN_SAMPLE_FOR_CANDIDATE, win_rate=0.2, avg_r_multiple=-0.5, expectancy=-0.5))
    db_session.add(LearnedRule(scope="pattern:volatility:ranging", condition={}, conclusion="already proposed", confidence=0.5, sample_size=8, status="candidate"))
    db_session.commit()

    summary = run_research_cycle(db_session, _FakeLLMClient(_VALID_PROPOSAL))
    assert summary["proposed"] == 0


def test_strategy_candidate_uses_latest_snapshot(db_session):
    strategy = _strategy(db_session, "declining_v1")
    old = StrategyPerformance(strategy_id=strategy.id, as_of=datetime.now(timezone.utc) - timedelta(days=2), window_trades=20, total_trades=20, win_rate=0.6, expectancy=0.8)
    new = StrategyPerformance(strategy_id=strategy.id, as_of=datetime.now(timezone.utc), window_trades=20, total_trades=40, win_rate=0.2, expectancy=-0.6)
    db_session.add_all([old, new])
    db_session.commit()

    summary = run_research_cycle(db_session, _FakeLLMClient(_VALID_PROPOSAL))
    assert summary["proposed"] == 1  # only the latest (unhealthy) snapshot should trigger a proposal


def test_validation_promotes_significant_losing_sample(db_session):
    strategy = _strategy(db_session, "bleeding_v1")
    asset = _asset(db_session, "BLEEDPERF")
    # low-variance, consistently negative sample -> should clear the z-test bar
    _trades_for_strategy(db_session, strategy, asset, r_multiples=[-1.0] * MIN_SAMPLE_FOR_VALIDATION)
    db_session.add(LearnedRule(scope=f"strategy:{strategy.code}", condition={}, conclusion="manual candidate", confidence=0.5, sample_size=8, status="candidate"))
    db_session.commit()

    run_research_cycle(db_session, _UnavailableLLMClient())  # validation runs regardless of LLM availability

    rule = db_session.query(LearnedRule).filter(LearnedRule.scope == f"strategy:{strategy.code}").first()
    assert rule.status == "validated"
    assert rule.validated_at is not None
    assert rule.sample_size == MIN_SAMPLE_FOR_VALIDATION


def test_validation_rejects_noisy_sample_around_zero(db_session):
    strategy = _strategy(db_session, "noisy_v1")
    asset = _asset(db_session, "NOISYPERF")
    r_multiples = [1.0, -1.0] * (MIN_SAMPLE_FOR_VALIDATION // 2)  # mean ~0, high variance
    _trades_for_strategy(db_session, strategy, asset, r_multiples=r_multiples)
    db_session.add(LearnedRule(scope=f"strategy:{strategy.code}", condition={}, conclusion="manual candidate", confidence=0.5, sample_size=8, status="candidate"))
    db_session.commit()

    run_research_cycle(db_session, _UnavailableLLMClient())

    rule = db_session.query(LearnedRule).filter(LearnedRule.scope == f"strategy:{strategy.code}").first()
    assert rule.status == "rejected"


def test_validation_leaves_thin_sample_as_candidate(db_session):
    strategy = _strategy(db_session, "toofew_v1")
    asset = _asset(db_session, "TOOFEWPERF")
    _trades_for_strategy(db_session, strategy, asset, r_multiples=[-1.0] * (MIN_SAMPLE_FOR_VALIDATION - 1))
    db_session.add(LearnedRule(scope=f"strategy:{strategy.code}", condition={}, conclusion="manual candidate", confidence=0.5, sample_size=8, status="candidate"))
    db_session.commit()

    run_research_cycle(db_session, _UnavailableLLMClient())

    rule = db_session.query(LearnedRule).filter(LearnedRule.scope == f"strategy:{strategy.code}").first()
    assert rule.status == "candidate"
    assert rule.validated_at is None


def test_pattern_scope_validation_walks_signal_chain(db_session):
    strategy = _strategy(db_session, "pattern_scope_v1")
    asset = _asset(db_session, "PATTERNSCOPE")
    _trades_for_pattern(db_session, asset, strategy, pattern_type="breakout", regime="ranging", r_multiples=[-1.2] * MIN_SAMPLE_FOR_VALIDATION)
    db_session.add(LearnedRule(scope="pattern:breakout:ranging", condition={}, conclusion="manual candidate", confidence=0.5, sample_size=8, status="candidate"))
    db_session.commit()

    run_research_cycle(db_session, _UnavailableLLMClient())

    rule = db_session.query(LearnedRule).filter(LearnedRule.scope == "pattern:breakout:ranging").first()
    assert rule.status == "validated"
