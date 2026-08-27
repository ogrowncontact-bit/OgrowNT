"""Channel/severity/incident-worthiness mapping — "PROMPT 14" §131, §59-61.

Pure lookup tables, no I/O — packages/events/tailer.py and
apps/api/websocket.py are the only callers. Kept separate from bus.py so
these mappings are trivially unit-testable without touching asyncio at all.
"""
from __future__ import annotations

# §131 — the 10 channels a dashboard client can subscribe to.
CHANNELS: tuple[str, ...] = (
    "market", "opportunities", "portfolio", "risk", "agents",
    "execution", "news", "events", "system", "alerts",
)

# Every TradingEvent.event_type this codebase can currently produce (the
# "trading_events" CHECK constraint, packages/shared/models.py), mapped onto
# the channel a dashboard user watching that domain would expect it on. An
# event_type not in this map (a future CHECK-constraint addition this map
# hasn't been updated for yet) falls back to "events" — the generic
# catch-all channel, never silently dropped.
TRADING_EVENT_CHANNEL: dict[str, str] = {
    "order_submitted": "execution",
    "order_filled": "execution",
    "order_rejected": "execution",
    "order_partially_filled": "execution",
    "order_cancelled": "execution",
    "reconciliation_mismatch": "execution",
    "broker_health_degraded": "execution",
    "position_opened": "portfolio",
    "position_closed": "portfolio",
    "risk_blocked": "risk",
    "no_trade": "risk",
    "portfolio_emergency_action": "risk",
    "loss_streak_detected": "risk",
    "trading_paused": "system",
    "trading_resumed": "system",
    "kill_switch_triggered": "system",
    "kill_switch_released": "system",
    "worker_restarted": "system",
    "crash_loop_protection_triggered": "system",
}
DEFAULT_CHANNEL = "events"

# TradingEvent has no severity column of its own (packages/shared/models.py's
# own docstring: it stitches moments from RiskDecision/AuditLog/order-
# lifecycle into one stream) — this derives one for the bus/UI rather than
# leaving every event "info". Anything not listed is "info".
CRITICAL_EVENT_TYPES: frozenset[str] = frozenset({
    "kill_switch_triggered", "crash_loop_protection_triggered", "reconciliation_mismatch",
})
WARNING_EVENT_TYPES: frozenset[str] = frozenset({
    "risk_blocked", "no_trade", "order_rejected", "loss_streak_detected",
    "portfolio_emergency_action", "broker_health_degraded", "trading_paused",
})


def severity_for_trading_event(event_type: str) -> str:
    if event_type in CRITICAL_EVENT_TYPES:
        return "critical"
    if event_type in WARNING_EVENT_TYPES:
        return "warning"
    return "info"


def channel_for_trading_event(event_type: str) -> str:
    return TRADING_EVENT_CHANNEL.get(event_type, DEFAULT_CHANNEL)


# §59-61 Incident Center: which TradingEvent types are worth turning into a
# durable, admin-workable Incident row (packages/shared/models.py::Incident)
# rather than just a bus message that scrolls away — deliberately a small,
# curated subset (this codebase's genuinely critical, already-existing
# detectors), not "every warning becomes an incident."
INCIDENT_WORTHY_EVENT_TYPES: dict[str, str] = {
    # event_type -> Incident.category
    "kill_switch_triggered": "system",
    "crash_loop_protection_triggered": "system",
    "reconciliation_mismatch": "broker",
}

# Alert.category (packages/shared/models.py) -> Incident.category. Only an
# Alert with severity="critical" is incident-worthy (packages/events/
# tailer.py) — this map only decides which Incident.category it lands in.
ALERT_CATEGORY_TO_INCIDENT_CATEGORY: dict[str, str] = {
    "risk": "risk",
    "loss": "risk",
    "emergency": "system",
    "system": "system",
    "trade": "execution",
    "market": "data",
    "news": "data",
    "learning": "agent",
}
