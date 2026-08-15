"""Learning Agent LLM half — docs/blueprint/04-agents-architecture.md#agent-13.

Turns one closed trade whose actual outcome diverged from what was expected
into a grounded hypothesis (packages/shared/models.py's TradeJournal). Never
applied automatically: the hypothesis is read-only context for a human or
the Research Agent, and even the Research Agent can only promote a general
rule after a separate DET statistical validation step
(packages/quant/learning/research.py).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from packages.llm.client import LLMClient, LLMResponseError, LLMUnavailableError
from packages.llm.prompts.learning_agent import SYSTEM_PROMPT

logger = logging.getLogger("llm.learning")


@dataclass(frozen=True)
class TradeHypothesis:
    hypothesis: str
    root_cause: str


def _build_user_content(
    *, strategy_code: str, asset_symbol: str, direction: str, regime: str | None,
    pattern_type: str | None, news_direction: str | None, outcome: str,
    pnl: float, r_multiple: float | None, exit_reason: str | None,
) -> str:
    return "\n".join(
        [
            f"STRATEGY: {strategy_code}",
            f"ASSET: {asset_symbol}",
            f"DIRECTION: {direction}",
            f"REGIME AT ENTRY: {regime or 'unknown'}",
            f"PATTERN AT ENTRY: {pattern_type or 'none'}",
            f"NEWS SIGNAL AT ENTRY: {news_direction or 'none'}",
            f"EXIT REASON: {exit_reason or 'unknown'}",
            f"OUTCOME: {outcome}",
            f"PNL: {pnl}",
            f"R_MULTIPLE: {r_multiple if r_multiple is not None else 'n/a'}",
            "EXPECTED_OUTCOME: win (the system only ever enters a trade it expects to win)",
        ]
    )


def generate_trade_hypothesis(client: LLMClient, **context: object) -> TradeHypothesis | None:
    if not client.is_available():
        return None

    try:
        raw = client.complete_json(SYSTEM_PROMPT, _build_user_content(**context))
    except (LLMUnavailableError, LLMResponseError):
        logger.exception("LLM hypothesis generation failed")
        return None
    except Exception:  # noqa: BLE001 - never let an API hiccup break trade close
        logger.exception("Unexpected error generating trade hypothesis")
        return None

    if not isinstance(raw, dict):
        logger.warning("Learning agent returned non-dict JSON, discarding: %r", raw)
        return None
    try:
        hypothesis = str(raw["hypothesis"]).strip()[:2000]
        root_cause = str(raw["root_cause"]).strip()[:200]
    except (KeyError, TypeError):
        logger.warning("Learning agent output missing required fields: %r", raw)
        return None
    if not hypothesis or not root_cause:
        return None
    return TradeHypothesis(hypothesis=hypothesis, root_cause=root_cause)
