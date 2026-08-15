"""News Intelligence interpretation — docs/blueprint/04-agents-architecture.md#agent-03.

Turns one real NewsItem into zero or more (asset, direction, impact,
confidence, horizon, rationale) reads. This is the ONLY function in the
codebase that turns LLM output into structured data used elsewhere — every
field is validated before being trusted; a malformed or out-of-universe
entry is dropped, not coerced or guessed into validity.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from packages.data.connectors.news.base import NewsItem
from packages.llm.client import LLMClient, LLMResponseError, LLMUnavailableError
from packages.llm.prompts.news_intelligence import SYSTEM_PROMPT

logger = logging.getLogger("llm.news_intelligence")

_VALID_DIRECTIONS = {"bullish", "bearish", "neutral"}
_VALID_IMPACTS = {"low", "medium", "high"}


@dataclass(frozen=True)
class NewsImpactResult:
    asset_symbol: str
    direction: str
    impact: str
    confidence: float
    horizon_hours: float
    rationale: str


def _build_user_content(item: NewsItem, asset_symbols: list[str]) -> str:
    return (
        f"HEADLINE: {item.headline}\n"
        f"SOURCE: {item.source}\n"
        f"CATEGORY: {item.category}\n"
        f"PUBLISHED_AT: {item.published_at.isoformat()}\n\n"
        f"ASSET UNIVERSE (use only these symbols): {', '.join(sorted(asset_symbols))}"
    )


def _validate_entries(raw: object, asset_symbols: list[str]) -> list[NewsImpactResult]:
    if not isinstance(raw, list):
        logger.warning("LLM interpretation returned non-list JSON, discarding: %r", raw)
        return []

    valid_symbols = set(asset_symbols)
    results: list[NewsImpactResult] = []
    for entry in raw:
        try:
            symbol = entry["asset_symbol"]
            direction = entry["direction"]
            impact = entry["impact"]
            confidence = float(entry["confidence"])
        except (KeyError, TypeError, ValueError):
            logger.warning("Skipping malformed LLM interpretation entry: %r", entry)
            continue

        if symbol not in valid_symbols:
            logger.warning("Dropping interpretation for out-of-universe symbol %r", symbol)
            continue
        if direction not in _VALID_DIRECTIONS or impact not in _VALID_IMPACTS:
            logger.warning("Dropping interpretation with invalid enum values: %r", entry)
            continue
        if not (0.0 <= confidence <= 1.0):
            logger.warning("Dropping interpretation with out-of-range confidence: %r", entry)
            continue

        results.append(
            NewsImpactResult(
                asset_symbol=symbol,
                direction=direction,
                impact=impact,
                confidence=confidence,
                horizon_hours=max(0.0, float(entry.get("horizon_hours", 12.0))),
                rationale=str(entry.get("rationale", ""))[:2000],
            )
        )
    return results


def interpret_news_item(client: LLMClient, item: NewsItem, asset_symbols: list[str]) -> list[NewsImpactResult]:
    if not client.is_available():
        logger.info("LLM not configured (ANTHROPIC_API_KEY unset) — skipping interpretation")
        return []
    if not asset_symbols:
        return []

    try:
        raw = client.complete_json(SYSTEM_PROMPT, _build_user_content(item, asset_symbols))
    except (LLMUnavailableError, LLMResponseError):
        logger.exception("LLM interpretation failed for headline %r", item.headline)
        return []
    except Exception:  # noqa: BLE001 - never let an API hiccup break the worker cycle
        logger.exception("Unexpected error interpreting headline %r", item.headline)
        return []

    return _validate_entries(raw, asset_symbols)
