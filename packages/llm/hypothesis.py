"""Autonomous Research Agent LLM half — "PROMPT 10" §13.

Writes the narrative fields (title/description/hypothesis/expected_effect)
of a `ResearchHypothesis` from DET-computed trigger evidence. Exactly the
same shape as `packages/llm/research.py::propose_rule`: honest `None` when
`ANTHROPIC_API_KEY` isn't configured (the caller,
`packages/research/hypothesis.py`, always has a DET-only template fallback
so hypothesis generation never actually depends on an LLM being
available), never trusted without the output-validation this module does
itself.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from packages.llm.client import LLMClient, LLMResponseError, LLMUnavailableError
from packages.llm.prompts.hypothesis_agent import SYSTEM_PROMPT

logger = logging.getLogger("llm.hypothesis")


@dataclass(frozen=True)
class HypothesisNarrative:
    title: str
    description: str
    hypothesis: str
    expected_effect: str


def _build_user_content(*, trigger: str, evidence: dict) -> str:
    lines = [f"TRIGGER: {trigger}"] + [f"{key.upper()}: {value}" for key, value in evidence.items()]
    return "\n".join(lines)


def propose_hypothesis(client: LLMClient, *, trigger: str, evidence: dict) -> HypothesisNarrative | None:
    if not client.is_available():
        return None

    try:
        raw = client.complete_json(SYSTEM_PROMPT, _build_user_content(trigger=trigger, evidence=evidence))
    except (LLMUnavailableError, LLMResponseError):
        logger.exception("LLM hypothesis proposal failed for trigger %r", trigger)
        return None
    except Exception:  # noqa: BLE001 - never let an API hiccup break the research cycle
        logger.exception("Unexpected error proposing hypothesis for trigger %r", trigger)
        return None

    if not isinstance(raw, dict):
        logger.warning("Hypothesis agent returned non-dict JSON, discarding: %r", raw)
        return None
    try:
        title = str(raw["title"]).strip()[:80]
        description = str(raw["description"]).strip()[:2000]
        hypothesis = str(raw["hypothesis"]).strip()[:1000]
        expected_effect = str(raw["expected_effect"]).strip()[:1000]
    except (KeyError, TypeError, ValueError):
        logger.warning("Hypothesis agent output missing/invalid required fields: %r", raw)
        return None

    if not title or not description or not hypothesis or not expected_effect:
        logger.warning("Hypothesis agent output failed validation (empty field): %r", raw)
        return None

    return HypothesisNarrative(title=title, description=description, hypothesis=hypothesis, expected_effect=expected_effect)
