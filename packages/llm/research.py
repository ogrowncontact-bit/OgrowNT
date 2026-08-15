"""Research Agent LLM half — docs/blueprint/04-agents-architecture.md#agent-14.

Proposes a candidate learned_rule explaining a pattern/strategy's poor
recent expectancy. Always written with status='candidate'
(packages/quant/learning/research.py) — never validated on the LLM's say-so,
and never applied to strategy behavior automatically.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from packages.llm.client import LLMClient, LLMResponseError, LLMUnavailableError
from packages.llm.prompts.research_agent import SYSTEM_PROMPT

logger = logging.getLogger("llm.research")


@dataclass(frozen=True)
class RuleProposal:
    condition: dict
    conclusion: str
    confidence: float


def _build_user_content(*, scope: str, stats: dict) -> str:
    lines = [f"SCOPE: {scope}"] + [f"{key.upper()}: {value}" for key, value in stats.items()]
    return "\n".join(lines)


def propose_rule(client: LLMClient, *, scope: str, stats: dict) -> RuleProposal | None:
    if not client.is_available():
        return None

    try:
        raw = client.complete_json(SYSTEM_PROMPT, _build_user_content(scope=scope, stats=stats))
    except (LLMUnavailableError, LLMResponseError):
        logger.exception("LLM rule proposal failed for scope %r", scope)
        return None
    except Exception:  # noqa: BLE001 - never let an API hiccup break the research cycle
        logger.exception("Unexpected error proposing rule for scope %r", scope)
        return None

    if not isinstance(raw, dict):
        logger.warning("Research agent returned non-dict JSON, discarding: %r", raw)
        return None
    try:
        condition = raw["condition"]
        conclusion = str(raw["conclusion"]).strip()[:1000]
        confidence = float(raw["confidence"])
    except (KeyError, TypeError, ValueError):
        logger.warning("Research agent output missing/invalid required fields: %r", raw)
        return None

    if not isinstance(condition, dict):
        logger.warning("Research agent condition was not a JSON object: %r", condition)
        return None
    if not conclusion or not (0.0 <= confidence <= 1.0):
        logger.warning("Research agent output failed validation: %r", raw)
        return None

    return RuleProposal(condition=condition, conclusion=conclusion, confidence=confidence)
