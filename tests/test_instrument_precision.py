"""packages/execution/instrument.py -- "PROMPT 13" §60-62."""
from __future__ import annotations

from packages.execution.instrument import get_instrument, validate_precision
from packages.shared.models import Asset


def _asset(**kwargs) -> Asset:
    defaults = dict(symbol="INSTRTEST", asset_class="crypto", is_active=True, tick_size=None, step_size=None, min_quantity=None, min_notional=None)
    defaults.update(kwargs)
    return Asset(**defaults)


def test_get_instrument_maps_asset_fields():
    asset = _asset(tick_size=0.01, step_size=0.001, min_quantity=0.001, min_notional=10.0)
    spec = get_instrument(asset)
    assert spec.symbol == "INSTRTEST"
    assert spec.tick_size == 0.01 and spec.min_notional == 10.0


def test_all_null_limits_pass_honestly_instead_of_inventing_a_default():
    asset = _asset()
    spec = get_instrument(asset)
    result = validate_precision(quantity=123.456, price=789.123, instrument=spec)
    assert result.ok is True
    assert result.violations == []


def test_below_min_quantity_is_flagged():
    spec = get_instrument(_asset(min_quantity=1.0))
    result = validate_precision(quantity=0.5, price=100.0, instrument=spec)
    assert result.ok is False
    assert any("below the instrument minimum" in v for v in result.violations)


def test_quantity_not_a_multiple_of_step_size_is_flagged():
    spec = get_instrument(_asset(step_size=0.1))
    result = validate_precision(quantity=0.35, price=100.0, instrument=spec)
    assert result.ok is False
    assert any("step_size" in v for v in result.violations)


def test_quantity_on_the_step_grid_passes():
    spec = get_instrument(_asset(step_size=0.1))
    result = validate_precision(quantity=0.3, price=100.0, instrument=spec)
    assert result.ok is True


def test_price_not_a_multiple_of_tick_size_is_flagged():
    spec = get_instrument(_asset(tick_size=0.01))
    result = validate_precision(quantity=1.0, price=100.005, instrument=spec)
    assert result.ok is False
    assert any("tick_size" in v for v in result.violations)


def test_below_min_notional_is_flagged():
    spec = get_instrument(_asset(min_notional=1000.0))
    result = validate_precision(quantity=1.0, price=10.0, instrument=spec)
    assert result.ok is False
    assert any("below the instrument minimum" in v and "notional" in v for v in result.violations)


def test_valid_order_against_every_limit_passes():
    spec = get_instrument(_asset(tick_size=0.01, step_size=0.01, min_quantity=0.01, min_notional=1.0))
    result = validate_precision(quantity=1.00, price=100.00, instrument=spec)
    assert result.ok is True
