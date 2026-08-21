"""LiveTradingFirewall — "PROMPT 13" §2, §26-27, §83, §97.

Three independent layers keep live trading unreachable this phase, by
design (no single point of failure):
  1. SystemState.trading_mode's own DB CHECK constraint — 'live' has never
     been a legal value (packages/shared/models.py, unchanged since
     "PROMPT 8"). Even a direct SQL UPDATE would be rejected by Postgres
     itself.
  2. THIS module — ENABLE_LIVE_TRADING is a hardcoded Python constant, not
     read from settings/env/DB/a config file, so there is no mutation path
     for an LLM, agent, strategy, or research module to ever flip it (§26).
     `LiveTradingFirewall.check()` is called from
     packages/execution/gate.py (every order, before it reaches
     order_manager) and from packages/execution/router.py (broker
     selection never even considers a 'live'-kind adapter).
  3. packages/execution/broker/live.py::LiveBrokerAdapter — every method
     raises immediately, so even a caller that bypassed both layers above
     and somehow obtained a live adapter instance can't use it.

§27's TWO-KEY SAFETY (SYSTEM_ENABLE + USER_ENABLE) is deliberately NOT
implemented as a working unlock mechanism this phase — LIVE stays blocked
regardless of any key's state, so building a real two-key unlock now would
be building the very door this phase is required to keep welded shut. See
docs/broker-execution-infrastructure.md's Divergências for what a future,
explicitly-approved live-trading phase would need to add here.
"""
from __future__ import annotations

from typing import Final

# Hardcoded — never a settings/env/DB-backed value (§26: "não permitir que
# LLM/Agent/Strategy/Research Engine alterem essa flag"). No mutation path
# exists anywhere in this codebase for ANY caller to change this constant
# at runtime; the only way to change it is a source-code change, reviewed
# like any other — and even that is guarded below.
ENABLE_LIVE_TRADING: Final[bool] = False

if ENABLE_LIVE_TRADING:  # pragma: no cover - a deliberate tripwire, not a real branch
    raise RuntimeError(
        "ENABLE_LIVE_TRADING must not be set True without also updating "
        "LiveTradingFirewall.check() below and completing the out-of-sample "
        "statistical validation gate documented in docs/blueprint/12-roadmap.md "
        "-- flipping this one constant alone must never be enough to enable "
        "live trading."
    )


class LiveTradingDisabledError(RuntimeError):
    pass


class LiveTradingFirewall:
    """Stateless — a namespace for the one check that matters, called from
    multiple independent pipeline layers (see module docstring, and §97's
    "mesmo que ENABLE_LIVE_TRADING seja alterado acidentalmente,
    LiveTradingFirewall continua bloqueando")."""

    @staticmethod
    def check(mode: str) -> None:
        if mode == "live":
            raise LiveTradingDisabledError(
                "LiveTradingFirewall: DENY ALL — live trading is permanently disabled this phase (§2)"
            )
        if mode not in ("paper", "sandbox", "simulation"):
            raise LiveTradingDisabledError(f"LiveTradingFirewall: unrecognized execution mode {mode!r}")
