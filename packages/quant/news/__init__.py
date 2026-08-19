"""News Intelligence — Prompt 6 (docs/news-intelligence.md).

Everything in this package is deterministic (DET): entity extraction,
asset mapping, sentiment, novelty, importance, deduplication, impact
scoring, momentum, event reactions. The only LLM-touched step in the whole
News Intelligence pipeline is packages/llm/news_intelligence.py's
per-(news, asset) direction/impact call — this package never calls an LLM,
so it works identically with or without ANTHROPIC_API_KEY configured.

A news item is a source of context, never an order — packages/risk/engine.py
is the only place a signal is approved or blocked, and this package's output
(NewsRiskGuard, opportunity contradiction penalties) can only ever reduce or
gate what the Risk/Opportunity Engines do, never execute a trade directly
(Prompt 6 §2/§43).
"""
