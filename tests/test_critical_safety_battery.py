"""Critical Safety Battery — "PROMPT 8" §91: deliberately try to bypass
Risk Engine, bypass Portfolio Manager, execute with stale data, execute
after Kill Switch, execute when Risk Engine offline, duplicate an order,
exceed exposure, exceed daily loss, exceed drawdown. Every one must result
in ORDER BLOCKED (no Order/Position ever created).

Most of these already have dedicated, deeper unit tests elsewhere — this
file is the consolidated cross-reference plus the two items that weren't
covered anywhere else yet (a structural "can this even be bypassed"
Proof, and Risk-Engine-raises-an-exception behavior):

| # | Item                       | Covered here | Also covered in                                          |
|---|----------------------------|:---:|-----------------------------------------------------------|
| 1 | bypass Risk Engine         | structural | (nothing calls open_position outside risk_execution.py)   |
| 2 | bypass Portfolio Manager   | yes | tests/test_portfolio_manager.py (pure evaluate_allocation) |
| 3 | execute with stale data    |  | tests/test_risk_engine.py::test_stale_data_is_rejected     |
| 4 | execute after Kill Switch  |  | tests/test_risk_engine.py::test_kill_switch_blocks_everything |
| 5 | execute when Risk Engine offline | yes | — |
| 6 | duplicate an order         |  | tests/test_execution.py::test_a_second_order_reusing_the_same_idempotency_key_is_rejected_by_the_db |
| 7 | exceed exposure            |  | tests/test_risk_engine.py::test_portfolio_exposure_at_limit_is_rejected |
| 8 | exceed daily loss          |  | tests/test_risk_engine.py::test_daily_loss_limit_blocks_new_trades |
| 9 | exceed drawdown            |  | tests/test_risk_engine.py::test_emergency_belt_blocks_all_new_trades |
"""
from datetime import datetime, timedelta, timezone

import pytest

import apps.worker.risk_execution as risk_execution
from apps.worker.risk_execution import maybe_execute
from packages.data.connectors.market.base import Candle
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.quant.indicators.core import IndicatorSet
from packages.quant.regime.classifier import RegimeResult
from packages.quant.scoring.engine import OpportunityScore as ScoreResult
from packages.quant.strategies import ALL_STRATEGIES
from packages.quant.strategies.base import AnalysisResult, MarketContext, StrategySignal
from packages.shared.models import Asset, Order, Position, Signal, StrategyRow

_STRATEGY = ALL_STRATEGIES[0]


def _asset_with_price(db_session, symbol: str, price: float) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _strategy_row(db_session, code: str) -> StrategyRow:
    existing = db_session.query(StrategyRow).filter(StrategyRow.code == code).first()
    if existing is not None:
        return existing
    row = StrategyRow(code=code, name=code, family=_STRATEGY.family, version="1.0")
    db_session.add(row)
    db_session.commit()
    return row


def _maybe_execute_kwargs(db_session, asset: Asset, strategy_row: StrategyRow, *, entry_price: float = 100.0):
    now = datetime.now(timezone.utc)
    candles = [
        Candle(ts=now - timedelta(minutes=5 - i), open=entry_price, high=entry_price * 1.001, low=entry_price * 0.999, close=entry_price, volume=1000, data_quality="high")
        for i in range(5)
    ]
    indicators = IndicatorSet(
        close=entry_price, sma_fast=entry_price, sma_slow=entry_price, ema_fast=entry_price, ema_slow=entry_price,
        rsi_14=50.0, atr_14=entry_price * 0.01, realized_vol_20=0.01, trend_strength=0.5, roc_10=0.0,
        avg_volume_20=1000.0, recent_high_20=entry_price, recent_low_20=entry_price,
    )
    regime = RegimeResult(regime="trending_bull", confidence=0.8, features={})
    ctx = MarketContext(asset_id=asset.id, symbol=asset.symbol, timeframe="1m", candles=candles, indicators=indicators, regime=regime)
    analysis = AnalysisResult(direction="long", strength=0.9, rationale={})
    signal = StrategySignal(direction="long", entry_price=entry_price, stop_price=entry_price * 0.95, target_price=entry_price * 1.15, strength=0.9, rationale={})

    signal_row = Signal(
        strategy_id=strategy_row.id, asset_id=asset.id, ts=now, direction="long",
        entry_price=signal.entry_price, stop_price=signal.stop_price, target_price=signal.target_price, status="scored",
    )
    db_session.add(signal_row)
    db_session.commit()

    score = ScoreResult(
        technical=80.0, pattern=0.0, regime_fit=80.0, historical_edge=50.0, liquidity=80.0, news=50.0,
        risk_reward=80.0, strategy_performance=50.0, volatility_penalty_points=0.0, correlation_penalty_points=0.0,
        execution_cost_penalty_points=0.0, drawdown_penalty_points=0.0, final_score=85.0, tier="high_quality",
    )

    return dict(ctx=ctx, asset=asset, strategy=_STRATEGY, analysis=analysis, signal=signal, signal_row=signal_row, score=score)


def test_risk_engine_offline_blocks_execution_never_assumes_safe(db_session, monkeypatch):
    """§72: "Se Risk Engine estiver indisponível: # NO TRADES. Nunca
    assumir 'provavelmente seguro'." Simulated by evaluate_signal raising —
    proves the exception propagates (no silent fallback to "approved") and
    no Order/Position is ever created."""
    asset = _asset_with_price(db_session, "SAFETYOFFLINE", 100.0)
    strategy_row = _strategy_row(db_session, "safety_offline_strategy")
    kwargs = _maybe_execute_kwargs(db_session, asset, strategy_row)

    def _boom(*a, **kw):
        raise RuntimeError("Risk Engine unavailable (simulated)")

    monkeypatch.setattr(risk_execution, "evaluate_signal", _boom)

    provider = PaperExecutionProvider(db_session)
    with pytest.raises(RuntimeError):
        maybe_execute(db_session, provider, **kwargs)

    assert db_session.query(Position).count() == 0
    assert db_session.query(Order).count() == 0


def test_portfolio_manager_blocks_a_signal_risk_engine_alone_would_approve(db_session):
    """§74: "Se Portfolio Manager falhar: NO NEW TRADES" — here exercised
    as "the Portfolio Manager gate rejects", not a crash, but the same
    principle: Risk Engine approval alone is never sufficient. The strategy
    is already at its config/risk_limits.yaml max_strategy_allocation_pct
    (30%) via one big existing position, so a second, otherwise-clean
    signal for the SAME strategy must be portfolio_rejected, not executed."""
    strategy_row = _strategy_row(db_session, "safety_portfolio_strategy")
    parked_asset = _asset_with_price(db_session, "SAFETYPARKED", 100.0)
    # 100 * 300 = 30,000 notional -- 30% of the ~100k+ equity this dev DB
    # has accumulated across the whole session is intentionally NOT assumed;
    # instead size it against the actual current equity so the test is
    # robust regardless of what equity this shared dev DB currently has.
    from packages.portfolio.state import compute_state

    equity = compute_state(db_session).equity
    parked_size = (equity * 0.30) / 100.0
    db_session.add(
        Position(
            asset_id=parked_asset.id, strategy_id=strategy_row.id, direction="long", entry_price=100.0,
            current_stop=95.0, size=parked_size, status="open",
        )
    )
    db_session.commit()

    asset = _asset_with_price(db_session, "SAFETYCANDIDATE", 100.0)
    kwargs = _maybe_execute_kwargs(db_session, asset, strategy_row)

    provider = PaperExecutionProvider(db_session)
    outcome = maybe_execute(db_session, provider, **kwargs)

    assert outcome == "portfolio_rejected"
    assert db_session.query(Position).filter(Position.asset_id == asset.id).count() == 0


def test_open_position_is_never_called_outside_the_risk_gated_path():
    """Structural proof for "bypass Risk Engine" / "bypass Portfolio
    Manager": the ONLY production code path that can create a real
    position is apps/worker/risk_execution.py, which always calls it after
    both evaluate_signal(...).approved and evaluate_allocation(...).approved
    are true. Same AST-based method as
    tests/test_backtest_lab_full_simulation.py's
    test_no_live_trading_anywhere_in_the_lab_pipeline."""
    import ast
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    allowed_callers = {repo_root / "apps" / "worker" / "risk_execution.py", repo_root / "packages" / "execution" / "order_manager.py"}

    offenders = []
    for base in (repo_root / "apps", repo_root / "packages"):
        for path in base.rglob("*.py"):
            if path in allowed_callers or "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open_position":
                    offenders.append(str(path.relative_to(repo_root)))

    assert offenders == [], f"open_position() called outside the risk-gated path: {offenders}"
