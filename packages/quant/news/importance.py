"""Event Importance — Prompt 6 §14: LOW / MEDIUM / HIGH / CRITICAL.

Rule-based from category plus surprise/urgency language in the headline —
deterministic, never an LLM guess (this whole package never calls one;
packages/llm/news_intelligence.py's per-asset direction/impact call is a
separate, independent step).
"""
from __future__ import annotations

import re

LOW, MEDIUM, HIGH, CRITICAL = "low", "medium", "high", "critical"
IMPORTANCE_LEVELS = (LOW, MEDIUM, HIGH, CRITICAL)

# Prompt 6 §14's own examples: central bank / major exchange / major
# institution collapse / geopolitical escalation are CRITICAL-by-default
# categories; earnings surprises / important releases / regulation are HIGH.
_CRITICAL_CATEGORIES = {"central_bank", "interest_rate", "security_breach", "banking"}
_HIGH_CATEGORIES = {
    "inflation", "cpi", "ppi", "employment", "gdp", "earnings", "geopolitics",
    "regulation", "crypto_regulation",
}
_MEDIUM_CATEGORIES = {"m_and_a", "legal", "supply_chain", "commodity", "etf", "energy", "currency"}

_CRITICAL_KEYWORDS = {
    "unexpected", "shock", "shocking", "emergency", "collapse", "collapses", "collapsed",
    "crisis", "halted", "halt", "suspends", "suspended", "default", "bankruptcy",
    "bankrupt", "war", "invasion", "attack", "failure", "fails", "failed",
}
_HIGH_KEYWORDS = {"surprise", "surprises", "surprised", "surge", "plunge", "crash", "record", "warns", "warning"}

_WORD_RE = re.compile(r"[a-z]+")


def classify_importance(category: str | None, headline: str, body: str | None = None) -> str:
    text = f"{headline} {body or ''}".lower()
    words = set(_WORD_RE.findall(text))

    if words & _CRITICAL_KEYWORDS:
        return CRITICAL
    if category in _CRITICAL_CATEGORIES:
        return CRITICAL if words & _HIGH_KEYWORDS else HIGH
    if words & _HIGH_KEYWORDS:
        return HIGH
    if category in _HIGH_CATEGORIES:
        return HIGH
    if category in _MEDIUM_CATEGORIES:
        return MEDIUM
    return LOW
