"""NewsProvider interface — docs/blueprint/04-agents-architecture.md#agent-03.

Ingestion is deterministic and must never fabricate a news item that wasn't
actually published — the same "no hallucinated data" principle as
MarketDataProvider (packages/data/connectors/market/base.py). Interpreting
*what a real item means* is the LLM's job (packages/llm), a separate step.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

NEWS_CATEGORIES = (
    "central_bank", "inflation", "employment", "gdp", "geopolitics",
    "regulation", "crypto", "earnings", "m_and_a", "other",
)


@dataclass(frozen=True)
class NewsItem:
    source: str
    published_at: datetime
    headline: str
    body: str | None
    raw_url: str | None
    category: str


class NewsProvider(Protocol):
    name: str

    def is_connected(self) -> bool: ...

    def get_recent_news(self, since: datetime, limit: int = 50) -> list[NewsItem]:
        """Items published at or after `since`, newest last. MUST return []
        rather than invent an item when the source has nothing new."""
        ...
