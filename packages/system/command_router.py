"""Command Bar safety classification — "PROMPT 14" §91-93, §136.

§93: "Comandos como 'buy'/'sell'/'close'/'increase risk'/'enable live'
devem ser tratados como UNAUTHORIZED nesta fase." This is the one property
that must be airtight (tests/test_command_center_red_team.py proves it
holds for every execution verb the spec names, and that this classifier is
the ONLY thing apps/api/routers/command_center.py consults before ever
touching the database — see that router's own docstring). The safe-QUERY
side is deliberately a small, curated keyword router below, not a full LLM
NLU pipeline — the same "nesta fase: implementar arquitetura" scoping the
prompt itself applies to the Notification Center (§90) and the live-trading
two-key unlock (packages/execution/firewall.py, "PROMPT 13" §27).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

QUERY = "query"
UNAUTHORIZED = "unauthorized"

# Deliberately broad and case-insensitive — a false positive (blocking a
# genuinely safe query that happens to contain "buy" as a noun, e.g. "why
# did the system buy BTC yesterday") is an acceptable cost in a trading
# system for never letting an execution verb slip through unclassified.
# Word-boundary matched so "buyer"/"closely" don't false-positive.
_EXECUTION_VERBS = (
    "buy", "sell", "close", "cancel", "increase risk", "decrease risk",
    "enable live", "disable kill switch", "override", "force execute",
    "place order", "submit order", "open position", "go live",
)
_EXECUTION_PATTERN = re.compile(r"\b(" + "|".join(re.escape(v) for v in _EXECUTION_VERBS) + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class CommandClassification:
    classification: str  # "query" | "unauthorized"
    reason: str


def classify_command(text: str) -> CommandClassification:
    if _EXECUTION_PATTERN.search(text):
        return CommandClassification(UNAUTHORIZED, 'execution commands are never authorized from the command bar ("PROMPT 14" §93)')
    return CommandClassification(QUERY, "read-only query")


# §91's example queries, mapped onto a small fixed set of intents —
# apps/api/routers/command_center.py owns the actual DB reads per intent
# (thin composition over already-existing endpoints' own queries, not new
# business logic worth hiding in this package).
INTENT_TOP_OPPORTUNITIES = "top_opportunities"
INTENT_RISK_SUMMARY = "risk_summary"
INTENT_UNDERPERFORMING_STRATEGIES = "underperforming_strategies"
INTENT_LAST_BLOCKED_TRADE = "last_blocked_trade"
INTENT_UNRECOGNIZED = "unrecognized"

_INTENT_KEYWORDS: tuple[tuple[str, str], ...] = (
    (INTENT_TOP_OPPORTUNITIES, "opportunit"),
    (INTENT_RISK_SUMMARY, "risk"),
    (INTENT_UNDERPERFORMING_STRATEGIES, "underperform"),
    (INTENT_UNDERPERFORMING_STRATEGIES, "strateg"),
    (INTENT_LAST_BLOCKED_TRADE, "blocked"),
)


def route_query_intent(text: str) -> str:
    lowered = text.lower()
    for intent, keyword in _INTENT_KEYWORDS:
        if keyword in lowered:
            return intent
    return INTENT_UNRECOGNIZED
