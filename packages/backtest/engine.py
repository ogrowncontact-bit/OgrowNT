"""Event-driven Backtest Engine — docs/blueprint/10-backtesting-paper-trading.md,
extended by "PROMPT 7" (docs/backtest-lab.md) with configurable execution
costs, execution latency, enriched metrics, an optional data-integrity gate,
and optional news-aware replay.

Walks real, already-persisted OHLCV bars forward one at a time, feeding the
strategy only `candles[0..i]` at step `i` (never a later bar) so there is no
look-ahead bias. Runs the same pipeline apps/worker/strategy_runner.py runs
live — indicators, regime classification, pattern detection, the strategy's
own analyze()/generate_signal(), the Opportunity Scoring Engine, and the
Risk Engine's sizing/safety-belt logic (packages/backtest/risk.py) — against
an isolated simulated portfolio (packages/backtest/portfolio.py) that never
touches the live paper account.

Honest limitations, stated up front rather than silently glossed over:
- Data source is whatever this deployment has actually persisted to
  `ohlcv` — there is no separate historical dataset. With only a mock
  market data provider running so far, that window is necessarily short;
  see docs/blueprint/12-roadmap.md's Phase 6 section for exactly how short.
- News signals are neutral (empty) by default; pass `news_aware=True` to
  replay real, look-ahead-safe `news_impact` rows via
  packages/backtest/news_replay.py — honestly sparse/empty for any window
  before the News Intelligence worker went live (docs/news-intelligence.md).
- No historical_edge/strategy_performance carry-over from live learning
  data: pulling in performance the system only learned *after* a given
  historical bar would itself be a form of look-ahead, so both stay
  neutral for every backtest run.
- Single asset, at most one open position at a time — see
  packages/backtest/risk.py for why the correlation guard doesn't apply.
- Execution latency (`ExecutionConfig.latency.bars`) delays *entries* only;
  exits fire on the same bar their condition is detected. Modeling exit
  latency too would double the loop's bookkeeping for a system that only
  ever paper-trades — a documented simplification, not an oversight.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import cast

from sqlalchemy.orm import Session

from packages.backtest.data_integrity import check_data_integrity
from packages.backtest.execution_models import ExecutionConfig, simulate_fill_configurable
from packages.backtest.metrics import compute_extra_metrics
from packages.backtest.news_replay import news_signals_as_of
from packages.backtest.portfolio import EquityPoint, SimPosition, SimTrade, SimulatedPortfolio
from packages.backtest.risk import evaluate_signal_for_backtest
from packages.data.connectors.market.base import Candle, DataQuality
from packages.quant.indicators.core import MIN_CANDLES_REQUIRED, compute_indicators
from packages.quant.patterns.detector import detect_all
from packages.quant.regime.classifier import NewsSignal, classify_regime
from packages.quant.scoring import build_scoring_inputs, compute_score
from packages.quant.strategies.base import MarketContext, Strategy
from packages.risk.config import RiskLimits, load_risk_limits
from packages.shared.models import OHLCV

TIERS_ELIGIBLE_FOR_RISK_REVIEW = {"possible", "high_quality", "exceptional"}
BASELINE_ATR_PCT = 0.01  # same convention as apps/worker/risk_execution.py


@dataclass(frozen=True)
class BacktestResult:
    num_trades: int
    net_return: float | None
    cagr_like_return: float | None
    win_rate: float | None
    profit_factor: float | None
    max_drawdown: float | None
    avg_trade: float | None
    expectancy: float | None
    sharpe_like: float | None
    equity_curve: list[dict]
    trades: list[dict]
    notes: dict = field(default_factory=dict)
    extra_metrics: dict = field(default_factory=dict)
    data_fingerprint: str | None = None


def _volatility_factor(ctx: MarketContext) -> float:
    atr, close = ctx.indicators.atr_14, ctx.indicators.close
    if not atr or not close:
        return 1.0
    return max(1.0, (atr / close) / BASELINE_ATR_PCT)


def _atr_pct(ctx: MarketContext) -> float | None:
    atr, close = ctx.indicators.atr_14, ctx.indicators.close
    if not atr or not close:
        return None
    return atr / close


def _check_exit(position: SimPosition, current: Candle, strategy: Strategy, regime: str) -> str | None:
    if position.direction == "long":
        if current.close <= position.stop_price:
            return "stop_hit"
        if position.target_price is not None and current.close >= position.target_price:
            return "target_hit"
    else:
        if current.close >= position.stop_price:
            return "stop_hit"
        if position.target_price is not None and current.close <= position.target_price:
            return "target_hit"
    if regime in strategy.worst_regimes:
        return "thesis_invalidated"
    return None


def _load_candles(db: Session, asset_id: int, timeframe: str, start_ts: datetime, end_ts: datetime) -> list[Candle]:
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe, OHLCV.ts >= start_ts, OHLCV.ts < end_ts)
        .order_by(OHLCV.ts.asc())
        .all()
    )
    return [
        Candle(
            ts=r.ts, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume,
            data_quality=cast(DataQuality, r.data_quality),  # DB CHECK constraint guarantees a valid value
        )
        for r in rows
    ]


def _data_fingerprint(candles: list[Candle]) -> str | None:
    """Lightweight reproducibility fingerprint (§48) -- not a cryptographic
    guarantee the underlying table never changed, just enough to tell two
    runs "the same window of the same asset/timeframe produced the exact
    same bars" apart from "something in the data shifted"."""
    if not candles:
        return None
    digest = hashlib.sha256()
    for c in candles:
        digest.update(f"{c.ts.isoformat()}|{c.open}|{c.high}|{c.low}|{c.close}|{c.volume}\n".encode())
    return digest.hexdigest()[:16]


def _max_drawdown_pct(equity_curve: list[EquityPoint]) -> float | None:
    if not equity_curve:
        return None
    peak = equity_curve[0].equity
    max_dd = 0.0
    for point in equity_curve:
        peak = max(peak, point.equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - point.equity) / peak * 100)
    return round(max_dd, 4)


def _sharpe(r_multiples: list[float]) -> float | None:
    if len(r_multiples) < 2:
        return None
    mean_r = sum(r_multiples) / len(r_multiples)
    variance = sum((r - mean_r) ** 2 for r in r_multiples) / (len(r_multiples) - 1)
    std = math.sqrt(variance)
    return round(mean_r / std, 4) if std > 0 else None


def _trade_dict(t: SimTrade) -> dict:
    return {
        "direction": t.direction, "entry_price": t.entry_price, "exit_price": t.exit_price, "size": t.size,
        "pnl": t.pnl, "r_multiple": t.r_multiple, "outcome": t.outcome,
        "opened_at": t.opened_at.isoformat(), "closed_at": t.closed_at.isoformat(), "exit_reason": t.exit_reason,
        "entry_fees": t.entry_fees, "exit_fees": t.exit_fees,
        "entry_slippage_bps": t.entry_slippage_bps, "exit_slippage_bps": t.exit_slippage_bps,
        "entry_regime": t.entry_regime,
    }


def _blocked_result(reason: str, **extra: object) -> BacktestResult:
    return BacktestResult(
        num_trades=0, net_return=None, cagr_like_return=None, win_rate=None, profit_factor=None,
        max_drawdown=None, avg_trade=None, expectancy=None, sharpe_like=None, equity_curve=[], trades=[],
        notes={"reason": reason, **extra},
    )


def _summarize(
    portfolio: SimulatedPortfolio, trades: list[SimTrade], initial_capital: float,
    data_fingerprint: str | None, risk_veto_counts: dict[str, int],
) -> BacktestResult:
    equity_curve = [
        {"ts": p.ts.isoformat(), "equity": p.equity, "cash": p.cash, "exposure_pct": p.exposure_pct, "drawdown_pct": p.drawdown_pct, "daily_pnl": p.daily_pnl}
        for p in portfolio.equity_curve
    ]
    final_equity = portfolio.equity_curve[-1].equity if portfolio.equity_curve else initial_capital
    net_return = round((final_equity - initial_capital) / initial_capital, 4) if initial_capital > 0 else None

    cagr_like_return = None
    if net_return is not None and len(portfolio.equity_curve) >= 2 and final_equity > 0:
        elapsed_days = max(1, (portfolio.equity_curve[-1].ts - portfolio.equity_curve[0].ts).days)
        years = elapsed_days / 365.25
        cagr_like_return = round((final_equity / initial_capital) ** (1 / years) - 1, 4)

    max_dd = _max_drawdown_pct(portfolio.equity_curve)

    if not trades:
        return BacktestResult(
            num_trades=0, net_return=net_return, cagr_like_return=cagr_like_return, win_rate=None,
            profit_factor=None, max_drawdown=max_dd, avg_trade=None, expectancy=None, sharpe_like=None,
            equity_curve=equity_curve, trades=[], notes={"reason": "no_trades_generated"},
            extra_metrics={"risk_veto_counts": risk_veto_counts} if risk_veto_counts else {},
            data_fingerprint=data_fingerprint,
        )

    wins = [t for t in trades if t.outcome == "win"]
    losses = [t for t in trades if t.outcome == "loss"]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    r_multiples = [t.r_multiple for t in trades if t.r_multiple is not None]
    net_pnl = sum(t.pnl for t in trades)

    extra_metrics = compute_extra_metrics(
        equity_curve=portfolio.equity_curve, trades=trades, initial_capital=initial_capital,
        net_pnl=net_pnl, max_drawdown_pct=max_dd, r_multiples=r_multiples,
    )
    extra_metrics["risk_veto_counts"] = risk_veto_counts

    return BacktestResult(
        num_trades=len(trades),
        net_return=net_return,
        cagr_like_return=cagr_like_return,
        win_rate=round(len(wins) / len(trades), 4),
        profit_factor=round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
        max_drawdown=max_dd,
        avg_trade=round(sum(t.pnl for t in trades) / len(trades), 4),
        expectancy=round(sum(r_multiples) / len(r_multiples), 4) if r_multiples else None,
        sharpe_like=_sharpe(r_multiples),
        equity_curve=equity_curve,
        trades=[_trade_dict(t) for t in trades],
        notes={},
        extra_metrics=extra_metrics,
        data_fingerprint=data_fingerprint,
    )


def run_backtest(
    db: Session, *, strategy: Strategy, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, initial_capital: float, risk_limits: RiskLimits | None = None,
    execution: ExecutionConfig | None = None, news_aware: bool = False, check_integrity: bool = True,
) -> BacktestResult:
    if check_integrity:
        integrity = check_data_integrity(db, asset_id, timeframe, start_ts, end_ts)
        if integrity.blocked:
            return _blocked_result(
                "data_integrity_blocked",
                issues=[{"severity": i.severity, "code": i.code, "detail": i.detail} for i in integrity.issues],
            )

    candles = _load_candles(db, asset_id, timeframe, start_ts, end_ts)
    return run_backtest_on_candles(
        db, strategy=strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe, candles=candles,
        initial_capital=initial_capital, risk_limits=risk_limits, execution=execution, news_aware=news_aware,
    )


def run_backtest_on_candles(
    db: Session, *, strategy: Strategy, asset_id: int, symbol: str, timeframe: str, candles: list[Candle],
    initial_capital: float, risk_limits: RiskLimits | None = None,
    execution: ExecutionConfig | None = None, news_aware: bool = False,
) -> BacktestResult:
    """Same event loop as run_backtest(), over a caller-supplied candle list
    instead of an `ohlcv` query. Exists for packages/backtest/stress_test.py:
    a stress scenario (a synthetic gap, crash, or reversed-price sequence)
    must never be written to the real `ohlcv` table -- other live cadences
    (the market scanner, the live strategy runner) read that table
    concurrently, and "READ/COMPUTE ONLY" (§65) rules out a backtest ever
    mutating shared state, even temporarily-then-restored. Synthetic
    scenarios are built as a plain in-memory list of Candle
    (packages/backtest/stress_data.py) and passed straight in here."""
    limits = risk_limits or load_risk_limits()
    execution_cfg = execution or ExecutionConfig()
    latency_bars = execution_cfg.latency.bars
    data_fingerprint = _data_fingerprint(candles)

    if len(candles) < MIN_CANDLES_REQUIRED + 1:
        return _blocked_result("insufficient_history", bars_available=len(candles), bars_required=MIN_CANDLES_REQUIRED + 1)

    portfolio = SimulatedPortfolio(initial_capital)
    open_position: SimPosition | None = None
    pending_entry: dict | None = None  # queued approved entry awaiting execution latency (see module docstring)
    trades: list[SimTrade] = []
    # Every reason evaluate_signal_for_backtest ever rejected a candidate
    # signal for -- surfaced in extra_metrics so a stress test (§60's kill
    # switch drill in particular) has real evidence the risk pipeline
    # actually fired, not just an absence of trades that could equally mean
    # "no signals were generated at all".
    risk_veto_counts: dict[str, int] = {}

    for i in range(MIN_CANDLES_REQUIRED, len(candles)):
        window = candles[: i + 1]  # no look-ahead: strategy only ever sees candles up to "now"
        current = window[-1]

        indicators = compute_indicators(window)
        regime_result = classify_regime(window)
        atr_pct = (indicators.atr_14 / indicators.close) if indicators.atr_14 and indicators.close else None

        if open_position is not None:
            exit_reason = _check_exit(open_position, current, strategy, regime_result.regime)
            if exit_reason is not None:
                side = "sell" if open_position.direction == "long" else "buy"
                fill = simulate_fill_configurable(
                    mid_price=current.close, volume=current.volume, qty=open_position.size, side=side,
                    fee_model=execution_cfg.fee_model, slippage_model=execution_cfg.slippage_model,
                    spread_bps=execution_cfg.spread_bps, atr_pct=atr_pct,
                )
                trades.append(
                    portfolio.close(
                        open_position, exit_price=fill.price, closed_at=current.ts, exit_reason=exit_reason,
                        exit_fees=fill.fees, exit_slippage_bps=fill.slippage_bps,
                    )
                )
                open_position = None

        portfolio.record_equity(current.ts, open_position, current.close)

        if pending_entry is not None and open_position is None and i >= pending_entry["execute_at_index"]:
            fill = simulate_fill_configurable(
                mid_price=current.close, volume=current.volume, qty=pending_entry["quantity"], side=pending_entry["side"],
                fee_model=execution_cfg.fee_model, slippage_model=execution_cfg.slippage_model,
                spread_bps=execution_cfg.spread_bps, atr_pct=atr_pct,
            )
            open_position = portfolio.open(
                direction=pending_entry["direction"], entry_price=fill.price, stop_price=pending_entry["stop_price"],
                target_price=pending_entry["target_price"], size=pending_entry["quantity"], opened_at=current.ts,
                entry_fees=fill.fees, entry_slippage_bps=fill.slippage_bps, entry_regime=pending_entry["regime"],
            )
            pending_entry = None

        if open_position is None and pending_entry is None and current.data_quality == "high":
            patterns = detect_all(window, indicators)
            ctx = MarketContext(asset_id=asset_id, symbol=symbol, timeframe=timeframe, candles=window, indicators=indicators, regime=regime_result)
            analysis = strategy.analyze(ctx)
            signal = strategy.generate_signal(ctx)

            if signal is not None:
                news_signals: list[NewsSignal] = news_signals_as_of(db, asset_id, current.ts) if news_aware else []
                inputs = build_scoring_inputs(ctx, strategy, analysis, signal, patterns=patterns, news_signals=news_signals)
                score = compute_score(inputs)

                if score.tier in TIERS_ELIGIBLE_FOR_RISK_REVIEW:
                    portfolio_state = portfolio.state(current.ts, None, current.close)
                    verdict = evaluate_signal_for_backtest(
                        tier=score.tier, risk_reward=signal.risk_reward, entry_price=signal.entry_price,
                        stop_price=signal.stop_price, confidence=analysis.strength, volatility_factor=_volatility_factor(ctx),
                        portfolio_state=portfolio_state, limits=limits,
                    )
                    if verdict.approved and verdict.approved_quantity:
                        side = "buy" if signal.direction == "long" else "sell"
                        if latency_bars <= 0:
                            fill = simulate_fill_configurable(
                                mid_price=current.close, volume=current.volume, qty=verdict.approved_quantity, side=side,
                                fee_model=execution_cfg.fee_model, slippage_model=execution_cfg.slippage_model,
                                spread_bps=execution_cfg.spread_bps, atr_pct=atr_pct,
                            )
                            open_position = portfolio.open(
                                direction=signal.direction, entry_price=fill.price, stop_price=signal.stop_price,
                                target_price=signal.target_price, size=verdict.approved_quantity, opened_at=current.ts,
                                entry_fees=fill.fees, entry_slippage_bps=fill.slippage_bps, entry_regime=regime_result.regime,
                            )
                        else:
                            pending_entry = {
                                "direction": signal.direction, "side": side, "quantity": verdict.approved_quantity,
                                "stop_price": signal.stop_price, "target_price": signal.target_price,
                                "execute_at_index": i + latency_bars, "regime": regime_result.regime,
                            }
                    else:
                        risk_veto_counts[verdict.reason] = risk_veto_counts.get(verdict.reason, 0) + 1

    if open_position is not None:
        last = candles[-1]
        side = "sell" if open_position.direction == "long" else "buy"
        fill = simulate_fill_configurable(
            mid_price=last.close, volume=last.volume, qty=open_position.size, side=side,
            fee_model=execution_cfg.fee_model, slippage_model=execution_cfg.slippage_model, spread_bps=execution_cfg.spread_bps,
        )
        trades.append(
            portfolio.close(
                open_position, exit_price=fill.price, closed_at=last.ts, exit_reason="backtest_end",
                exit_fees=fill.fees, exit_slippage_bps=fill.slippage_bps,
            )
        )
        portfolio.record_equity(last.ts, None, last.close)

    return _summarize(portfolio, trades, initial_capital, data_fingerprint, risk_veto_counts)
