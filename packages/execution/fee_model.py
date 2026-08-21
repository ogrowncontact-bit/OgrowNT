"""FeeModel — moved here from packages/backtest/execution_models.py
("PROMPT 13" §63-64) so packages/execution (a lower-level, shared package)
doesn't have to import packages/backtest to reuse it — that direction is
architecturally backwards (packages/backtest already imports FROM
packages/execution/fills.py, never the other way, and apps/worker must
never transitively import packages/backtest at all — docs/blueprint/
01-repo-structure.md). packages/backtest/execution_models.py re-exports
FeeModel/PROVIDER_FEE_RATES from here under the same names, so every
existing backtest-side import (packages/backtest/engine.py, sensitivity.py,
stress_test.py, walkforward_optimization.py, tests/test_backtest_v2_engine.py)
keeps working completely unchanged — this is the exact same class object,
just correctly homed.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.execution.fills import FEE_RATE

FEE_KINDS = ("percentage", "fixed", "tiered", "provider_specific")

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


def default_fee_model() -> FeeModel:
    return FeeModel(kind="percentage", rate=FEE_RATE)
