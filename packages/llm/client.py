"""LLM client — the only place packages/llm talks to Anthropic's API.

Structural half of "LLM ≠ Trading Engine" (docs/blueprint/00-overview.md
§6, docs/blueprint/01-repo-structure.md §Regras de dependência): this
package is never imported by packages/execution, so nothing an LLM returns
can reach an order no matter what a prompt says. The other half — LLM
output only ever *interprets*, never *decides* — is enforced by the callers
(packages/llm/news_intelligence.py) validating everything before it's used.

Requires ANTHROPIC_API_KEY. If unset, is_available() is False and callers
skip interpretation rather than fabricate one — same "no hallucinated data"
rule applied to LLM output as to market/news data.
"""
from __future__ import annotations

import json
import logging

from packages.shared.settings import get_settings

logger = logging.getLogger("llm.client")


class LLMUnavailableError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.anthropic_api_key
        self._model = model or settings.llm_model
        self._client = None
        if self._api_key:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)

    def is_available(self) -> bool:
        return self._client is not None

    def complete_json(self, system_prompt: str, user_content: str, max_tokens: int = 1024) -> list | dict:
        """Sends one message, returns the parsed JSON from the reply text.
        Raises LLMUnavailableError / LLMResponseError rather than returning
        a guessed fallback — callers decide how to handle those (typically:
        log and skip this item, per docs/blueprint/00-overview.md)."""
        if self._client is None:
            raise LLMUnavailableError("ANTHROPIC_API_KEY not configured")

        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return _parse_json_block(text)


def _parse_json_block(text: str) -> list | dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json") :]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"LLM reply was not valid JSON: {text[:200]!r}") from exc
