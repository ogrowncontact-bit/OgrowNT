"""Feature research + ablation testing — "PROMPT 10" §22-25.

Feature research (§22-24) reads what's already tracked per (pattern_type,
regime) in `packages/quant/learning/` Phase 4's `PatternPerformance` table
— momentum/volatility/volume/market-structure signals are literally the
named pattern types `packages/quant/patterns/detector.py` already detects
and scores by regime, so "which features correlate with performance, and
is that regime-dependent" is a read over existing data, not a new compute
engine. §23's "não assumir correlation = causation" is enforced by never
returning more than a correlation + sample size — no causal language.

Ablation (§25) answers "does this specific feature filter add value" by
wrapping an existing `Strategy` in `FeatureAblationStrategy`, which drops
any signal that fails a `packages.research.dsl` condition — the SAME
strategy, differing only in whether the filter is applied, run through the
SAME `packages.backtest.engine.run_backtest` both times. No new
backtesting math; one new, thin `Strategy`-protocol wrapper.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.backtest.engine import BacktestResult, run_backtest
from packages.quant.strategies.base import AnalysisResult, MarketContext, RiskProfile, Strategy, StrategySignal
from packages.research import dsl
from packages.risk.config import RiskLimits
from packages.shared.models import PatternPerformance

MIN_SAMPLE_FOR_FEATURE_EVIDENCE = 8  # same magnitude as packages/quant/learning/research.py's MIN_SAMPLE_FOR_CANDIDATE


@dataclass(frozen=True)
class FeatureSignal:
    pattern_type: str
    regime: str
    sample_size: int
    win_rate: float | None
    expectancy: float | None
    regime_dependent: bool


def research_feature_signals(db: Session, *, min_sample: int = MIN_SAMPLE_FOR_FEATURE_EVIDENCE) -> list[FeatureSignal]:
    """§22-24: every (pattern_type, regime) combination with enough sample
    to say anything at all, flagged `regime_dependent` when the same
    pattern_type's expectancy sign differs across regimes it's been seen
    in — a correlation observation, never a causal claim.
    """
    rows = db.execute(
        select(PatternPerformance).where(PatternPerformance.sample_size >= min_sample)
    ).scalars().all()

    by_pattern: dict[str, list[PatternPerformance]] = {}
    for row in rows:
        by_pattern.setdefault(row.pattern_type, []).append(row)

    signals = []
    for pattern_type, pattern_rows in by_pattern.items():
        signs = {(r.expectancy > 0) for r in pattern_rows if r.expectancy is not None}
        regime_dependent = len(signs) > 1
        for row in pattern_rows:
            signals.append(
                FeatureSignal(
                    pattern_type=pattern_type, regime=row.regime, sample_size=row.sample_size,
                    win_rate=row.win_rate, expectancy=row.expectancy, regime_dependent=regime_dependent,
                )
            )
    return signals


@dataclass
class FeatureAblationStrategy:
    """Wraps any existing `Strategy` (satisfies the same Protocol —
    `packages/quant/strategies/base.py`) and drops any signal that fails
    `feature_filter` (a `packages.research.dsl` condition over the same
    `IndicatorSet` fields every strategy already reads). `feature_filter=None`
    behaves identically to the wrapped strategy — the WITHOUT-feature arm
    of an ablation test.

    The identity fields are copied (not `@property`-delegated) in
    `__post_init__` because `Strategy`'s Protocol declares them as plain
    settable attributes — a read-only `@property` doesn't structurally
    satisfy that, per mypy.
    """

    base: Strategy
    feature_filter: dict | None = None

    def __post_init__(self) -> None:
        self.code = self.base.code
        self.name = self.base.name
        self.version = self.base.version
        self.family = self.base.family
        self.best_regimes = self.base.best_regimes
        self.worst_regimes = self.base.worst_regimes

    def analyze(self, ctx: MarketContext) -> AnalysisResult:
        return self.base.analyze(ctx)

    def calculate_expected_value(self, ctx: MarketContext, analysis: AnalysisResult) -> float:
        return self.base.calculate_expected_value(ctx, analysis)

    def regime_fit(self, regime: str) -> float:
        return self.base.regime_fit(regime)

    def get_risk_profile(self) -> RiskProfile:
        return self.base.get_risk_profile()

    def generate_signal(self, ctx: MarketContext) -> StrategySignal | None:
        signal = self.base.generate_signal(ctx)
        if signal is None or self.feature_filter is None:
            return signal
        context = _indicator_context(ctx)
        if not dsl.evaluate_condition(self.feature_filter, context):
            return None
        return signal


def _indicator_context(ctx: MarketContext) -> dict:
    context = {field: getattr(ctx.indicators, field, None) for field in dsl.ALLOWED_FIELDS if hasattr(ctx.indicators, field)}
    context["regime"] = ctx.regime.regime
    context["regime_confidence"] = ctx.regime.confidence
    return context


@dataclass(frozen=True)
class AblationResult:
    feature_filter: dict
    with_feature: BacktestResult
    without_feature: BacktestResult
    expectancy_delta: float | None
    adds_value: bool | None
    reason: str


def run_ablation(
    db: Session, *, base_strategy: Strategy, feature_filter: dict, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, initial_capital: float, risk_limits: RiskLimits | None = None,
) -> AblationResult:
    """§25's "strategy with feature vs strategy without feature". `dsl.validate`
    runs first so a malformed filter fails loudly, not mid-backtest."""
    validation = dsl.validate(feature_filter)
    if not validation.valid:
        raise dsl.DslValidationError(f"invalid feature_filter: {validation.errors}")

    without_feature = run_backtest(
        db, strategy=FeatureAblationStrategy(base=base_strategy, feature_filter=None), asset_id=asset_id, symbol=symbol,
        timeframe=timeframe, start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits,
    )
    with_feature = run_backtest(
        db, strategy=FeatureAblationStrategy(base=base_strategy, feature_filter=feature_filter), asset_id=asset_id, symbol=symbol,
        timeframe=timeframe, start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits,
    )

    if with_feature.expectancy is None or without_feature.expectancy is None:
        return AblationResult(
            feature_filter=feature_filter, with_feature=with_feature, without_feature=without_feature,
            expectancy_delta=None, adds_value=None, reason="insufficient trades on one or both arms to judge",
        )

    delta = round(with_feature.expectancy - without_feature.expectancy, 6)
    adds_value = delta > 0 and with_feature.num_trades >= MIN_SAMPLE_FOR_FEATURE_EVIDENCE
    reason = (
        f"filtering by this feature changed expectancy by {delta:+.4f}R over {with_feature.num_trades} filtered trades "
        f"(vs {without_feature.num_trades} unfiltered)"
        if with_feature.num_trades >= MIN_SAMPLE_FOR_FEATURE_EVIDENCE
        else f"only {with_feature.num_trades} filtered trades -- below the {MIN_SAMPLE_FOR_FEATURE_EVIDENCE} needed to judge"
    )
    return AblationResult(
        feature_filter=feature_filter, with_feature=with_feature, without_feature=without_feature,
        expectancy_delta=delta, adds_value=adds_value if with_feature.num_trades >= MIN_SAMPLE_FOR_FEATURE_EVIDENCE else None,
        reason=reason,
    )
