"""RateLimitManager — "PROMPT 13" §51-52.

Architecture-ready, not exercised against a real rate limit: PaperBrokerAdapter
makes no network calls at all (packages/execution/adapters/paper.py's own
docstring), so nothing in this codebase's own worker/API processes can ever
actually approach a limit — same "built for real, tested via synthetic
exhaustion since only one honest implementation exists" precedent as
packages/data/connectors/market/failover.py ("PROMPT 12"). A genuine token
bucket per (broker, category) so a future real adapter has a real throttle
to plug into, not a stub that would need rewriting later.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    capacity: int
    tokens: float
    refill_per_second: float
    last_refill: float


class RateLimitManager:
    """One bucket per (broker_name, category) — e.g. ("paper", "orders") vs
    ("paper", "market_data") never share a budget, since a real venue's
    order-submission and market-data limits are independent quotas."""

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], _Bucket] = {}

    def configure(self, *, broker: str, category: str, capacity: int, refill_per_second: float) -> None:
        self._buckets[(broker, category)] = _Bucket(
            capacity=capacity, tokens=float(capacity), refill_per_second=refill_per_second, last_refill=time.monotonic(),
        )

    def _bucket(self, broker: str, category: str) -> _Bucket | None:
        return self._buckets.get((broker, category))

    def _refill(self, bucket: _Bucket) -> None:
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_per_second)
        bucket.last_refill = now

    def headroom(self, *, broker: str, category: str) -> float | None:
        """Remaining budget as a 0-1 fraction of capacity, or None when this
        (broker, category) pair was never configured (§52's "throttle when
        close to the limit" has nothing to throttle against)."""
        bucket = self._bucket(broker, category)
        if bucket is None:
            return None
        self._refill(bucket)
        return bucket.tokens / bucket.capacity if bucket.capacity else 0.0

    def try_acquire(self, *, broker: str, category: str, cost: int = 1) -> bool:
        """§52 — True and consumes `cost` tokens if there's room; False (and
        consumes nothing) if the caller should throttle/pause instead. An
        unconfigured pair always allows (nothing to limit against)."""
        bucket = self._bucket(broker, category)
        if bucket is None:
            return True
        self._refill(bucket)
        if bucket.tokens < cost:
            return False
        bucket.tokens -= cost
        return True
