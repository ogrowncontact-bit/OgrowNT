"""RetryPolicy — "PROMPT 13" §53-54.

The allowlist IS the safety mechanism: retrying a read (health_check,
get_order, get_positions, get_balances, get_open_orders, get_trades) is
always safe to repeat — it has no side effect. Retrying create_order is
NEVER automatic (§53 "nunca repetir cegamente: order submission", §54 "se
submit ocorrer e resposta desaparecer: UNKNOWN... não reenviar
imediatamente. Primeiro: query order status") — order_manager.py's own
idempotency_key already makes a *deliberate* resubmission safe (a genuine
retry hits the DB's unique constraint instead of duplicating), but that is
a human/next-cycle decision, never something this policy silently loops on
by itself.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

# Read-only, side-effect-free BrokerAdapter operations — see module
# docstring. create_order/cancel_order/replace_order are deliberately
# absent: a cancel that appears to fail may have actually succeeded, and
# blindly retrying it (or an order submission) is exactly the "duplicate
# order" risk §12/§50 exist to prevent.
RETRYABLE_OPERATIONS = frozenset({
    "health_check", "get_account", "get_balances", "get_positions",
    "get_open_orders", "get_order", "get_trades", "get_market_data",
    "get_fees", "get_instrument",
})


def is_retryable(operation: str) -> bool:
    return operation in RETRYABLE_OPERATIONS


def retry_with_backoff(
    operation: str,
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.1,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Only ever call this for an operation is_retryable() approves —
    callers that pass a non-idempotent operation get a hard error rather
    than a silent retry (§53's line is enforced here, not just documented)."""
    if not is_retryable(operation):
        raise ValueError(f"{operation!r} is not a safe/idempotent operation to retry — see RETRYABLE_OPERATIONS")

    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - re-raised below if exhausted
            last_exc = exc
            if attempt < max_attempts - 1:
                sleep(base_delay_seconds * (2**attempt))
    assert last_exc is not None  # max_attempts >= 1 guarantees at least one iteration ran
    raise last_exc
