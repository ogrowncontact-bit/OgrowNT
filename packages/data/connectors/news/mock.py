"""Mock news provider — Phase 4 default (NEWS_PROVIDER=mock).

Generates plausible-sounding but entirely synthetic headlines from a fixed
template pool, deterministic per time bucket so repeated calls within the
same window are stable (real news doesn't refresh every second either).

THIS IS NOT A REAL NEWS SOURCE — every headline is fictional. Before Phase
4's News Intelligence Agent acts on anything real, or before any live
capital, replace this with a real adapter (e.g. a news API or RSS feed)
behind the same NewsProvider protocol:

    TODO(real-news-data): implement a provider against a real news API
    (e.g. NewsAPI, Alpha Vantage News, a curated RSS list) and switch
    NEWS_PROVIDER away from "mock" in production config.

Deliberately does NOT tag headlines with specific assets — real news
ingestion doesn't know what's relevant either; that judgment call belongs
to the interpretation step (packages/llm), not to ingestion.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from packages.data.connectors.news.base import NewsItem

_TEMPLATES: dict[str, list[str]] = {
    "central_bank": [
        "Central bank holds policy rate steady, signals data-dependent path ahead",
        "Policymakers hint at rate cut as growth momentum slows",
        "Minutes reveal split committee on inflation outlook",
    ],
    "inflation": [
        "Headline inflation print comes in above consensus estimates",
        "Core inflation eases for a third straight month",
        "Producer prices surprise to the downside",
    ],
    "employment": [
        "Monthly payrolls report beats expectations, unemployment rate steady",
        "Jobless claims tick higher, labor market shows signs of cooling",
        "Wage growth decelerates despite tight labor market",
    ],
    "gdp": [
        "Quarterly GDP growth revised upward on stronger consumer spending",
        "Economic growth slows more than expected in preliminary estimate",
    ],
    "geopolitics": [
        "Trade tension escalates as new tariffs are announced",
        "Diplomatic talks ease regional tensions, markets react cautiously",
    ],
    "regulation": [
        "Regulator proposes new disclosure rules for large asset managers",
        "Antitrust probe opened into major technology merger",
    ],
    "crypto": [
        "Exchange reports notable shift in on-chain accumulation patterns",
        "Regulatory clarity proposal for digital assets gains legislative support",
        "Large holder wallet activity spikes ahead of a scheduled network upgrade",
    ],
    "earnings": [
        "Quarterly results top analyst estimates, guidance raised",
        "Earnings miss expectations, shares under pressure in aftermarket trading",
    ],
    "m_and_a": [
        "Company announces definitive agreement to acquire smaller competitor",
        "Merger talks reported between two industry peers",
    ],
}

_SOURCES = ["Reuters", "Bloomberg", "Associated Press", "Financial Times", "MarketWatch"]
_PUBLISH_PROBABILITY_PER_BUCKET = 0.35  # a news item shows up roughly a third of the time
_BUCKET_MINUTES = 15


class MockNewsProvider:
    name = "mock"

    def __init__(self) -> None:
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    def get_recent_news(self, since: datetime, limit: int = 50) -> list[NewsItem]:
        now = datetime.now(timezone.utc)
        bucket = int(now.timestamp() // (_BUCKET_MINUTES * 60))
        rng = random.Random(f"news:{bucket}")

        if rng.random() > _PUBLISH_PROBABILITY_PER_BUCKET:
            return []

        category = rng.choice(list(_TEMPLATES.keys()))
        headline = rng.choice(_TEMPLATES[category])
        published_at = now - timedelta(seconds=rng.randint(0, _BUCKET_MINUTES * 60))
        if published_at < since:
            return []

        item = NewsItem(
            source=rng.choice(_SOURCES),
            published_at=published_at,
            headline=headline,
            body=None,
            raw_url=None,
            category=category,
        )
        return [item][:limit]
