"""News Intelligence Agent — "PROMPT 9" §25. Wraps the already-computed
`AssetNewsContext` (`packages/quant/news/context.py`, Prompt 6) — the same
recent-news view the Scoring Engine reads — into a directional read:
confidence/impact-weighted vote across `RecentNewsItem.direction` (already
produced by the existing DET+LLM news pipeline, itself independently
gated by the sovereign Risk Engine's News Risk Guard). Distinct from the
Sentiment Agent below, which reports tone only and is explicitly never
directional (Prompt 6 §11: "SENTIMENT NÃO É DIREÇÃO").
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus, signal_from_direction_strength

AGENT_CODE = "news_intelligence"
_IMPACT_WEIGHT = {"low": 0.3, "medium": 0.6, "high": 1.0}
_DIRECTION_SIGN = {"bullish": 1, "bearish": -1, "neutral": 0}


def analyze(ctx: AgentContext) -> AgentMessage:
    news = ctx.news_context
    if news is None or not news.recent_news:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0,
            evidence={"recent_news_count": 0}, rationale="no recent news for this asset",
        )

    weighted_sum, weight_total = 0.0, 0.0
    for item in news.recent_news:
        weight = _IMPACT_WEIGHT.get(item.impact, 0.3) * item.confidence
        weighted_sum += weight * _DIRECTION_SIGN.get(item.direction, 0)
        weight_total += weight

    if weight_total == 0:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0,
            evidence={"recent_news_count": len(news.recent_news)}, rationale="recent news carries no directional weight",
        )

    net = weighted_sum / weight_total  # -1..1
    direction = None if abs(net) < 0.15 else ("long" if net > 0 else "short")
    strength = round(min(1.0, abs(net)), 4)
    signal = signal_from_direction_strength(direction, strength)
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=signal, confidence=strength if direction else 0.0,
        evidence={"recent_news_count": len(news.recent_news), "net_direction_score": round(net, 4), "avg_source_quality": news.avg_source_quality},
        rationale=f"news-weighted direction score={round(net, 4)} over {len(news.recent_news)} item(s)",
    )
