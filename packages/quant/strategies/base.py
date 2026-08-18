"""Strategy Engine interface — docs/blueprint/04-agents-architecture.md#agent-07.

Every strategy is a stateless, pluggable unit: given a MarketContext it reads
market data and produces at most one candidate signal. Nothing here executes
anything — see docs/blueprint/12-roadmap.md, Execution Engine is Phase 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import IndicatorSet
from packages.quant.regime.classifier import RegimeResult

Direction = Literal["long", "short"]


@dataclass(frozen=True)
class MarketContext:
    asset_id: int
    symbol: str
    timeframe: str
    candles: list[Candle]  # chronological ascending, latest last
    indicators: IndicatorSet
    regime: RegimeResult


@dataclass(frozen=True)
class AnalysisResult:
    direction: Direction | None
    strength: float  # 0.0 (no read) - 1.0 (maximally confident)
    rationale: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StrategySignal:
    direction: Direction
    entry_price: float
    stop_price: float
    target_price: float
    strength: float
    rationale: dict = field(default_factory=dict)

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry_price - self.stop_price)
        if risk == 0:
            return 0.0
        reward = abs(self.target_price - self.entry_price)
        return reward / risk


@dataclass(frozen=True)
class RiskProfile:
    family: str
    typical_risk_reward: float
    best_regimes: frozenset[str]
    worst_regimes: frozenset[str]
    notes: str = ""


class Strategy(Protocol):
    code: str
    name: str
    version: str
    family: str
    best_regimes: frozenset[str]
    worst_regimes: frozenset[str]

    def analyze(self, ctx: MarketContext) -> AnalysisResult:
        """Read the market and form a directional view, with no side effects."""
        ...

    def generate_signal(self, ctx: MarketContext) -> StrategySignal | None:
        """Turn an analysis into a concrete entry/stop/target, or None."""
        ...

    def calculate_expected_value(self, ctx: MarketContext, analysis: AnalysisResult) -> float:
        """Cheap internal ranking score, NOT the Opportunity Score.

        Phase 2 has no trade history yet (Learning Engine / historical edge
        arrive Phase 5), so this is deliberately simple: confidence weighted
        by regime fit. It exists so strategies can rank their own candidates
        before scoring, not to replace docs/blueprint/07-scoring-engine.md.
        """
        ...

    def regime_fit(self, regime: str) -> float:
        if regime in self.best_regimes:
            return 1.0
        if regime in self.worst_regimes:
            return 0.0
        return 0.5

    def get_risk_profile(self) -> RiskProfile:
        """Static, declarative risk characteristics for this strategy —
        Prompt 3 §5/§14. Informational only: the Risk Engine
        (packages/risk) is what actually sizes/gates a position; this is
        what the dashboard's "why" panel and the Risk Engine's own future
        per-strategy tuning read, not a second source of truth for sizing.
        """
        ...


class StrategyBase:
    """Concrete base implementing the parts of Strategy that are the same for
    every strategy (regime_fit, calculate_expected_value), so each strategy
    only has to implement analyze()/generate_signal() plus its class
    attributes. Structurally still satisfies the Strategy protocol above.
    """

    code: str
    name: str
    version: str
    family: str
    best_regimes: frozenset[str] = frozenset()
    worst_regimes: frozenset[str] = frozenset()

    def regime_fit(self, regime: str) -> float:
        if regime in self.best_regimes:
            return 1.0
        if regime in self.worst_regimes:
            return 0.0
        return 0.5

    def calculate_expected_value(self, ctx: MarketContext, analysis: AnalysisResult) -> float:
        return analysis.strength * self.regime_fit(ctx.regime.regime)

    def get_risk_profile(self) -> RiskProfile:
        # Every concrete strategy already takes risk_reward as a constructor
        # parameter (Phase 6's parameter-stability refactor) -- reused here
        # rather than declaring a second, possibly-drifting copy of the
        # same number.
        return RiskProfile(
            family=self.family,
            typical_risk_reward=getattr(self, "risk_reward", 2.0),
            best_regimes=self.best_regimes,
            worst_regimes=self.worst_regimes,
        )
