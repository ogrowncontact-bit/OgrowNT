"""Instrument precision & validation — "PROMPT 13" §60-62.

`Instrument` (§60) is computed from Asset's own tick_size/step_size/
min_quantity/min_notional columns (packages/shared/models.py) rather than a
separate persisted table — in this single-venue-per-asset system an
instrument IS an asset; a second table would only ever hold a 1:1 shadow
copy of these four numbers. See docs/broker-execution-infrastructure.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.shared.models import Asset


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    asset_class: str
    tick_size: float | None
    step_size: float | None
    min_quantity: float | None
    min_notional: float | None
    contract_type: str | None
    trading_hours: dict | None


def get_instrument(asset: Asset) -> InstrumentSpec:
    return InstrumentSpec(
        symbol=asset.symbol,
        asset_class=asset.asset_class,
        tick_size=asset.tick_size,
        step_size=asset.step_size,
        min_quantity=asset.min_quantity,
        min_notional=asset.min_notional,
        contract_type=asset.asset_class,
        trading_hours=asset.trading_hours,
    )


def _round_to_step(value: float, step: float) -> float:
    return round(round(value / step) * step, 10)


@dataclass(frozen=True)
class PrecisionValidation:
    ok: bool
    violations: list[str] = field(default_factory=list)


def validate_precision(*, quantity: float, price: float, instrument: InstrumentSpec) -> PrecisionValidation:
    """§61-62 — a NULL limit is honestly skipped (not yet known for this
    asset), never treated as "anything goes" nor as "reject everything."
    Step/tick checks use a small epsilon since floating point division
    almost never lands on an exact multiple even when a human would call it
    "on-grid" (e.g. 0.0003 / 0.0001)."""
    violations: list[str] = []
    epsilon = 1e-9

    if instrument.min_quantity is not None and quantity < instrument.min_quantity:
        violations.append(f"quantity {quantity} is below the instrument minimum {instrument.min_quantity}")
    if instrument.step_size is not None and instrument.step_size > 0:
        remainder = abs(quantity - _round_to_step(quantity, instrument.step_size))
        if remainder > epsilon:
            violations.append(f"quantity {quantity} is not a multiple of step_size {instrument.step_size}")
    if instrument.tick_size is not None and instrument.tick_size > 0:
        remainder = abs(price - _round_to_step(price, instrument.tick_size))
        if remainder > epsilon:
            violations.append(f"price {price} is not a multiple of tick_size {instrument.tick_size}")
    if instrument.min_notional is not None:
        notional = quantity * price
        if notional < instrument.min_notional:
            violations.append(f"notional {notional:.4f} is below the instrument minimum {instrument.min_notional}")

    return PrecisionValidation(ok=not violations, violations=violations)
