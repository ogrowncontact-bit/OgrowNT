"""packages/execution/fees.py + packages/execution/fee_model.py --
"PROMPT 13" §63-64."""
from __future__ import annotations

from packages.execution.fee_model import FEE_RATE, PROVIDER_FEE_RATES
from packages.execution.fees import FeeEngine


def test_crypto_taker_matches_provider_fee_rates_table():
    fee = FeeEngine().compute_fee(asset_class="crypto", price=100.0, qty=10.0, liquidity="taker")
    assert fee == round(1000.0 * PROVIDER_FEE_RATES["crypto_spot_taker"], 4)


def test_crypto_maker_is_cheaper_than_taker():
    engine = FeeEngine()
    taker = engine.compute_fee(asset_class="crypto", price=100.0, qty=10.0, liquidity="taker")
    maker = engine.compute_fee(asset_class="crypto", price=100.0, qty=10.0, liquidity="maker")
    assert maker < taker


def test_forex_uses_the_forex_ecn_rate():
    fee = FeeEngine().compute_fee(asset_class="forex", price=1.1, qty=10_000.0, liquidity="taker")
    assert fee == round(1.1 * 10_000.0 * PROVIDER_FEE_RATES["forex_ecn"], 4)


def test_equity_uses_the_equities_retail_rate():
    fee = FeeEngine().compute_fee(asset_class="equity", price=100.0, qty=10.0, liquidity="taker")
    assert fee == round(1000.0 * PROVIDER_FEE_RATES["equities_retail"], 4)


def test_unmapped_asset_class_falls_back_to_flat_rate_not_a_fabricated_number():
    fee = FeeEngine().compute_fee(asset_class="commodity", price=100.0, qty=10.0)
    assert fee == round(1000.0 * FEE_RATE, 4)


def test_rate_for_exposes_the_underlying_rate_directly():
    engine = FeeEngine()
    assert engine.rate_for(asset_class="crypto", liquidity="taker") == PROVIDER_FEE_RATES["crypto_spot_taker"]
    assert engine.rate_for(asset_class="unknown_class") == FEE_RATE
