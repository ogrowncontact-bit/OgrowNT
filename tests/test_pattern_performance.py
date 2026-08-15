from packages.quant.patterns.performance import record_trade_outcome
from packages.shared.models import PatternPerformance


def test_first_trade_initializes_performance(db_session):
    perf = record_trade_outcome(db_session, pattern_type="breakout", regime="trending_bull", r_multiple=2.0, is_win=True)
    assert perf.sample_size == 1
    assert perf.win_rate == 1.0
    assert perf.avg_r_multiple == 2.0
    assert perf.expectancy == 2.0


def test_running_average_updates_correctly(db_session):
    record_trade_outcome(db_session, pattern_type="momentum", regime="ranging", r_multiple=1.0, is_win=True)
    record_trade_outcome(db_session, pattern_type="momentum", regime="ranging", r_multiple=-1.0, is_win=False)
    perf = db_session.get(PatternPerformance, ("momentum", "ranging"))
    assert perf.sample_size == 2
    assert perf.win_rate == 0.5
    assert perf.avg_r_multiple == 0.0
    assert perf.expectancy == 0.0


def test_different_regimes_tracked_separately(db_session):
    record_trade_outcome(db_session, pattern_type="trend", regime="trending_bull", r_multiple=3.0, is_win=True)
    record_trade_outcome(db_session, pattern_type="trend", regime="ranging", r_multiple=-2.0, is_win=False)

    bull_perf = db_session.get(PatternPerformance, ("trend", "trending_bull"))
    ranging_perf = db_session.get(PatternPerformance, ("trend", "ranging"))
    assert bull_perf.sample_size == 1
    assert bull_perf.win_rate == 1.0
    assert ranging_perf.sample_size == 1
    assert ranging_perf.win_rate == 0.0


def test_none_r_multiple_does_not_corrupt_average(db_session):
    record_trade_outcome(db_session, pattern_type="anomaly", regime="high_volatility", r_multiple=2.0, is_win=True)
    perf = record_trade_outcome(db_session, pattern_type="anomaly", regime="high_volatility", r_multiple=None, is_win=True)
    assert perf.sample_size == 2
    assert perf.win_rate == 1.0
    assert perf.avg_r_multiple == 2.0  # unaffected by the None entry
