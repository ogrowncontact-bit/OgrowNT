"""Sentiment Engine — Prompt 6 §10-11, §22.

Classifies the TONE of a headline/body — VERY_BULLISH .. VERY_BEARISH,
UNKNOWN when no sentiment-bearing word is found — via a deterministic
financial-tone lexicon, not an LLM call (this whole package never calls
one; packages/llm/news_intelligence.py's separate LLM step produces the
*price-impact direction* call, a different, independent signal).

Prompt 6 §11 is explicit: "SENTIMENT NÃO É DIREÇÃO" — a bullish-toned
headline does not imply the price will rise (an already-priced-in beat can
still sell off). Sentiment is stored and surfaced as one input among many,
never converted into an assumed price direction anywhere in this package.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.shared.models import NewsEvent, NewsImpact

VERY_BULLISH = "very_bullish"
BULLISH = "bullish"
NEUTRAL = "neutral"
BEARISH = "bearish"
VERY_BEARISH = "very_bearish"
UNKNOWN = "unknown"

# Deliberately not exhaustive — a curated financial-news lexicon, documented
# as heuristic (no NLP/embedding model available in this environment).
_POSITIVE_WORDS = {
    "surge", "surges", "surged", "soar", "soars", "soared", "rally", "rallies", "rallied",
    "jump", "jumps", "jumped", "gain", "gains", "gained", "beat", "beats", "outperform",
    "outperforms", "upgrade", "upgraded", "upgrades", "record", "strong", "strength",
    "robust", "optimism", "optimistic", "bullish", "boost", "boosts", "boosted", "rebound",
    "rebounds", "recovery", "recovers", "expand", "expands", "expansion", "growth", "rose",
    "rises", "rising", "climb", "climbs", "climbed", "higher", "exceed", "exceeds",
    "exceeded", "raise", "raised", "raises", "accelerate", "accelerates", "upside",
    "positive", "confidence", "stabilize", "stabilizes", "stabilized", "improve",
    "improves", "improved", "resilient", "milestone", "breakthrough",
}
_NEGATIVE_WORDS = {
    "plunge", "plunges", "plunged", "crash", "crashes", "crashed", "slump", "slumps",
    "slumped", "sink", "sinks", "sank", "tumble", "tumbles", "tumbled", "fall", "falls",
    "falling", "fell", "drop", "drops", "dropped", "miss", "misses", "missed", "downgrade",
    "downgraded", "downgrades", "weak", "weakness", "recession", "bearish", "decline",
    "declines", "declining", "declined", "concern", "concerns", "warn", "warns", "warning",
    "crisis", "collapse", "collapses", "collapsed", "default", "layoff", "layoffs", "cut",
    "cuts", "slowdown", "slows", "slowing", "disappoint", "disappoints", "disappointed",
    "disappointing", "turmoil", "volatility", "uncertain", "uncertainty", "risk", "risks",
    "shortage", "shortages", "probe", "investigation", "lawsuit", "breach", "fraud",
}

_WORD_RE = re.compile(r"[a-z]+")


@dataclass(frozen=True)
class SentimentResult:
    sentiment: str
    confidence: float
    positive_hits: int
    negative_hits: int


def classify_sentiment(headline: str, body: str | None = None) -> SentimentResult:
    text = f"{headline} {body or ''}".lower()
    words = _WORD_RE.findall(text)
    pos = sum(1 for w in words if w in _POSITIVE_WORDS)
    neg = sum(1 for w in words if w in _NEGATIVE_WORDS)
    total_hits = pos + neg

    if total_hits == 0:
        return SentimentResult(UNKNOWN, 0.0, 0, 0)

    score = (pos - neg) / total_hits
    confidence = round(min(1.0, total_hits / 4), 4)

    if score >= 0.6:
        sentiment = VERY_BULLISH
    elif score >= 0.2:
        sentiment = BULLISH
    elif score > -0.2:
        sentiment = NEUTRAL
    elif score > -0.6:
        sentiment = BEARISH
    else:
        sentiment = VERY_BEARISH

    return SentimentResult(sentiment, confidence, pos, neg)


_BULLISH_SENTIMENTS = {VERY_BULLISH, BULLISH}
_BEARISH_SENTIMENTS = {VERY_BEARISH, BEARISH}


@dataclass(frozen=True)
class SentimentShift:
    asset_id: int
    recent_bullish_share: float | None  # last `recent_hours`
    baseline_bullish_share: float | None  # last `baseline_hours`
    recent_count: int
    baseline_count: int
    shift: float | None  # recent - baseline, signed; None if either window is empty
    detected: bool  # abs(shift) >= threshold and both windows have enough samples


MIN_SAMPLES_FOR_SHIFT = 3
SHIFT_DETECTION_THRESHOLD = 0.25  # a 25-point swing in bullish share


def _bullish_share(sentiments: list[str]) -> float | None:
    scored = [s for s in sentiments if s in _BULLISH_SENTIMENTS or s in _BEARISH_SENTIMENTS]
    if not scored:
        return None
    return sum(1 for s in scored if s in _BULLISH_SENTIMENTS) / len(scored)


def compute_sentiment_shift(
    db: Session, asset_id: int, *, recent_hours: float = 2.0, baseline_hours: float = 24.0
) -> SentimentShift:
    """Prompt 6 §22: compares the bullish share of recent news sentiment
    against the longer baseline window for one asset. A shift is a
    descriptive signal only — never converted into a trade by this
    function or any caller (§22: "Não transformar automaticamente em
    trade")."""
    now = datetime.now(timezone.utc)
    baseline_cutoff = now - timedelta(hours=baseline_hours)
    recent_cutoff = now - timedelta(hours=recent_hours)

    rows = db.execute(
        select(NewsEvent.sentiment, NewsEvent.published_at)
        .join(NewsImpact, NewsImpact.news_event_id == NewsEvent.id)
        .where(NewsImpact.asset_id == asset_id, NewsEvent.published_at >= baseline_cutoff)
    ).all()

    baseline_sentiments = [r.sentiment for r in rows]
    recent_sentiments = [r.sentiment for r in rows if r.published_at >= recent_cutoff]

    recent_share = _bullish_share(recent_sentiments)
    baseline_share = _bullish_share(baseline_sentiments)

    shift = None
    detected = False
    if recent_share is not None and baseline_share is not None:
        shift = round(recent_share - baseline_share, 4)
        enough_samples = len(recent_sentiments) >= MIN_SAMPLES_FOR_SHIFT and len(baseline_sentiments) >= MIN_SAMPLES_FOR_SHIFT
        detected = enough_samples and abs(shift) >= SHIFT_DETECTION_THRESHOLD

    return SentimentShift(
        asset_id=asset_id, recent_bullish_share=recent_share, baseline_bullish_share=baseline_share,
        recent_count=len(recent_sentiments), baseline_count=len(baseline_sentiments),
        shift=shift, detected=detected,
    )
