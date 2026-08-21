"""FeeEngine — "PROMPT 13" §63-64.

Wires the FeeModel/PROVIDER_FEE_RATES machinery (packages/execution/
fee_model.py — moved there from packages/backtest/execution_models.py this
phase specifically so this module could reuse it) into PaperBrokerAdapter's
fill path (packages/execution/broker/paper.py), replacing
packages/execution/fills.py's single hardcoded flat FEE_RATE for the FEE
component only — fills.py's price/spread/slippage math is untouched, still
exactly what the Backtest Engine's default path and every pre-existing
test expect.

Fee tiers here are the SAME illustrative placeholder rates
PROVIDER_FEE_RATES already defines — not duplicated, just mapped from
Asset.asset_class + liquidity onto the keys that dict already has. An
asset_class with no entry (index/commodity/etf/future/bond/option) falls
back to the flat baseline rather than a fabricated per-class number this
codebase has no real source for.
"""
from __future__ import annotations

from packages.execution.fee_model import PROVIDER_FEE_RATES, FeeModel
from packages.execution.fills import FEE_RATE

# asset_class -> (taker_provider_key, maker_provider_key). Only the classes
# PROVIDER_FEE_RATES actually has real (if illustrative) entries for.
_ASSET_CLASS_PROVIDER_KEYS: dict[str, tuple[str, str]] = {
    "crypto": ("crypto_spot_taker", "crypto_spot_maker"),
    "forex": ("forex_ecn", "forex_ecn"),
    "equity": ("equities_retail", "equities_retail"),
}


class FeeEngine:
    """Stateless — a thin lookup, not a class that needs its own instance
    state; kept as a class (rather than a bare function) so
    BrokerAdapter.get_fees() and PaperBrokerAdapter's fill path share one
    obvious call site name, matching every other *Engine in this codebase."""

    def get_fee_model(self, *, asset_class: str, liquidity: str = "taker") -> FeeModel:
        keys = _ASSET_CLASS_PROVIDER_KEYS.get(asset_class)
        if keys is None:
            return FeeModel(kind="percentage", rate=FEE_RATE)
        provider = keys[0] if liquidity == "taker" else keys[1]
        return FeeModel(kind="provider_specific", provider=provider, rate=FEE_RATE)

    def compute_fee(self, *, asset_class: str, price: float, qty: float, liquidity: str = "taker") -> float:
        model = self.get_fee_model(asset_class=asset_class, liquidity=liquidity)
        return model.compute(price=price, qty=qty)

    def rate_for(self, *, asset_class: str, liquidity: str = "taker") -> float:
        keys = _ASSET_CLASS_PROVIDER_KEYS.get(asset_class)
        if keys is None:
            return FEE_RATE
        provider = keys[0] if liquidity == "taker" else keys[1]
        return PROVIDER_FEE_RATES.get(provider, FEE_RATE)
