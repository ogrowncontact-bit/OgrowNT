"""packages/system/command_router.py -- "PROMPT 14" §91-93."""
from __future__ import annotations

import pytest

from packages.system.command_router import (
    INTENT_LAST_BLOCKED_TRADE,
    INTENT_RISK_SUMMARY,
    INTENT_TOP_OPPORTUNITIES,
    INTENT_UNDERPERFORMING_STRATEGIES,
    INTENT_UNRECOGNIZED,
    QUERY,
    UNAUTHORIZED,
    classify_command,
    route_query_intent,
)

_EXECUTION_INPUTS = (
    "buy 10 BTC now",
    "sell my ETH position",
    "close all positions",
    "cancel the pending order",
    "increase risk on this trade",
    "decrease risk immediately",
    "enable live trading",
    "disable kill switch",
    "override the safety belt",
    "force execute this signal",
    "place order for AAPL",
    "submit order now",
    "open position on GBPUSD",
    "go live with real money",
)


@pytest.mark.parametrize("text", _EXECUTION_INPUTS)
def test_every_execution_verb_the_spec_names_is_classified_unauthorized(text):
    result = classify_command(text)
    assert result.classification == UNAUTHORIZED


@pytest.mark.parametrize("text", [t.upper() for t in _EXECUTION_INPUTS])
def test_classification_is_case_insensitive(text):
    assert classify_command(text).classification == UNAUTHORIZED


def test_a_word_boundary_match_does_not_false_positive_on_substrings():
    # "buyer"/"closely" contain "buy"/"close" as substrings but are not the
    # execution verbs themselves -- the trailing \b in the pattern requires
    # a word boundary right after "buy"/"close", which does not exist here
    # since "e" immediately follows in both words.
    assert classify_command("who is the biggest buyer of BTC this week").classification == QUERY
    assert classify_command("explain the situation closely").classification == QUERY


def test_safe_queries_are_classified_query():
    assert classify_command("show me the best opportunities").classification == QUERY
    assert classify_command("why is risk high right now").classification == QUERY
    assert classify_command("summarize today's performance").classification == QUERY


def test_route_query_intent_matches_expected_keywords():
    assert route_query_intent("show me the top opportunities") == INTENT_TOP_OPPORTUNITIES
    assert route_query_intent("what is our risk exposure") == INTENT_RISK_SUMMARY
    assert route_query_intent("which strategies are underperforming") == INTENT_UNDERPERFORMING_STRATEGIES
    assert route_query_intent("explain the last blocked trade") == INTENT_LAST_BLOCKED_TRADE
    assert route_query_intent("what is the weather today") == INTENT_UNRECOGNIZED
