"""Configurable Fee / Slippage / Execution-Latency models — "PROMPT 7" §8-10.

`packages/execution/fills.py`'s `simulate_fill` stays exactly as it is: it's
shared with live paper trading (`packages/execution/adapters/paper.py`) and
nothing here should risk changing what that path does. This module is a
strictly *additive*, backtest-only layer — `default_fee_model()` and
`default_slippage_model()` reproduce `fills.py`'s constants bit-for-bit, so a
backtest that doesn't pass a custom model gets identical numbers to before
this module existed. Only when a caller (parameter/cost/slippage sensitivity
analysis, the Strategy Lab UI's "risk model" picker) explicitly supplies a
different `FeeModel`/`SlippageModel`/`latency_bars` does behaviour change.

§8 "Nunca assumir fees = 0 como padrão de produção" is satisfied by
`default_fee_model()` never being a zero-fee model — see FEE_RATE below.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.execution.fills import BASE_SLIPPAGE_BPS, FEE_RATE, MAX_VOLUME_RATIO_FOR_SLIPPAGE, SPREAD_BPS

# Same convention as packages/backtest/engine.py's BASELINE_ATR_PCT /
# apps/worker/risk_execution.py: 1% ATR/price is treated as "normal"
# volatility; VOLATILITY_BASED slippage scales above that baseline.
BASELINE_ATR_PCT = 0.01

FEE_KINDS = ("percentage", "fixed", "tiered", "provider_specific")
SLIPPAGE_KINDS = ("fixed", "percentage", "volatility_based", "liquidity_based")

# Illustrative, clearly-labeled placeholder rates for a handful of common
# venue types -- NOT real fee schedules for any specific broker/exchange.
# A real integration would source these from the actual provider's fee API/
# published schedule (see packages/data/connectors' provider-abstraction
# pattern) rather than hardcoding them here.
PROVIDER_FEE_RATES: dict[str, float] = {
    "crypto_spot_taker": 0.0010,
    "crypto_spot_maker": 0.0004,
    "forex_ecn": 0.00007,
    "equities_retail": 0.0005,
}


@dataclass(frozen=True)
class FeeModel:
    kind: str = "percentage"
    rate: float = FEE_RATE
    fixed_amount: float = 0.0
    # Ascending (notional_threshold, rate) pairs; the highest threshold the
    # trade's notional meets or exceeds wins. An empty tuple with kind
    # "tiered" falls back to `rate` (equivalent to a flat percentage fee).
    tiers: tuple[tuple[float, float], ...] = ()
    provider: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in FEE_KINDS:
            raise ValueError(f"unknown fee model kind: {self.kind!r} (expected one of {FEE_KINDS})")

    def compute(self, *, price: float, qty: float) -> float:
        notional = price * qty
        if self.kind == "fixed":
            return round(self.fixed_amount, 4)
        if self.kind == "tiered":
            rate = self.rate
            for threshold, tier_rate in sorted(self.tiers):
                if notional >= threshold:
                    rate = tier_rate
            return round(notional * rate, 4)
        if self.kind == "provider_specific":
            rate = PROVIDER_FEE_RATES.get(self.provider or "", self.rate)
            return round(notional * rate, 4)
        return round(notional * self.rate, 4)  # percentage


@dataclass(frozen=True)
class SlippageModel:
    kind: str = "liquidity_based"
    slippage_bps: float = BASE_SLIPPAGE_BPS
    fixed_amount: float = 0.0
    max_volume_ratio: float = MAX_VOLUME_RATIO_FOR_SLIPPAGE

    def __post_init__(self) -> None:
        if self.kind not in SLIPPAGE_KINDS:
            raise ValueError(f"unknown slippage model kind: {self.kind!r} (expected one of {SLIPPAGE_KINDS})")

    def price_offset(self, *, mid_price: float, qty: float, volume: float, atr_pct: float | None = None) -> float:
        """Absolute price units of slippage (always >= 0; caller applies the
        sign for buy vs. sell)."""
        if self.kind == "fixed":
            return round(self.fixed_amount, 8)
        if self.kind == "volatility_based":
            factor = 1.0
            if atr_pct is not None and atr_pct > 0:
                factor = max(1.0, atr_pct / BASELINE_ATR_PCT)
            return round(mid_price * (self.slippage_bps * factor / 10_000), 8)
        if self.kind == "liquidity_based":
            volume_ratio = (qty / volume) if volume else 1.0
            bps = self.slippage_bps * (1 + min(self.max_volume_ratio, volume_ratio))
            return round(mid_price * (bps / 10_000), 8)
        return round(mid_price * (self.slippage_bps / 10_000), 8)  # percentage


@dataclass(frozen=True)
class LatencyModel:
    """Bars of delay between a signal being approved and its fill — §10.
    Bar-count (not wall-clock seconds) because the engine is bar-driven; a
    `bars=1` delay on a 1m timeframe is a ~1 minute signal-to-execution lag,
    on 15m a ~15 minute lag, matching the spec's "especialmente importante
    para 1m/5m/15m" framing without inventing a separate clock."""

    bars: int = 0

    def __post_init__(self) -> None:
        if self.bars < 0:
            raise ValueError("latency bars cannot be negative")


@dataclass(frozen=True)
class SimulatedFillV2:
    price: float
    fees: float
    slippage_bps: float


def default_fee_model() -> FeeModel:
    return FeeModel(kind="percentage", rate=FEE_RATE)


def default_slippage_model() -> SlippageModel:
    return SlippageModel(kind="liquidity_based", slippage_bps=BASE_SLIPPAGE_BPS, max_volume_ratio=MAX_VOLUME_RATIO_FOR_SLIPPAGE)


def default_latency_model() -> LatencyModel:
    return LatencyModel(bars=0)


def simulate_fill_configurable(
    *, mid_price: float, volume: float, qty: float, side: str,
    fee_model: FeeModel, slippage_model: SlippageModel, spread_bps: float = SPREAD_BPS, atr_pct: float | None = None,
) -> SimulatedFillV2:
    """Same cost direction convention as packages/execution/fills.py's
    simulate_fill: spread + slippage always work against the trader,
    regardless of side. With default_fee_model()/default_slippage_model()
    and spread_bps=SPREAD_BPS this reproduces simulate_fill's numbers
    exactly (see tests/test_backtest_execution_models.py)."""
    half_spread = mid_price * (spread_bps / 10_000) / 2
    slippage = slippage_model.price_offset(mid_price=mid_price, qty=qty, volume=volume, atr_pct=atr_pct)
    slippage_bps_effective = (slippage / mid_price * 10_000) if mid_price else 0.0

    fill_price = mid_price + half_spread + slippage if side == "buy" else mid_price - half_spread - slippage
    fees = fee_model.compute(price=fill_price, qty=qty)

    return SimulatedFillV2(price=round(fill_price, 8), fees=round(fees, 4), slippage_bps=round(slippage_bps_effective, 2))


@dataclass(frozen=True)
class ExecutionConfig:
    """Bundle passed into run_backtest() — the "RISK MODEL" / cost knobs the
    Strategy Lab UI exposes per §44. All fields default to exactly today's
    behaviour (see module docstring)."""

    fee_model: FeeModel = field(default_factory=default_fee_model)
    slippage_model: SlippageModel = field(default_factory=default_slippage_model)
    latency: LatencyModel = field(default_factory=default_latency_model)
    spread_bps: float = SPREAD_BPS
