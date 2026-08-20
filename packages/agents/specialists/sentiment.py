"""Sentiment Agent — "PROMPT 9" §26. Wraps
`packages/quant/news/sentiment.py::compute_sentiment_shift` — deliberately
NEVER directional (Prompt 6 §11: "SENTIMENT NÃO É DIREÇÃO" — a bullish tone
does not mean price rises, an already-priced-in beat can still sell off).
This agent's only signal is a risk_flag when a real bullish/bearish share
shift is detected between the recent and baseline windows — describing
that the market's tone has moved, without ever claiming to know which way
price will follow.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus

AGENT_CODE = "sentiment"


def analyze(ctx: AgentContext) -> AgentMessage:
    news = ctx.news_context
    shift = news.sentiment_shift if news is not None else None
    if shift is None or shift.shift is None:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0,
            evidence={"reason": "insufficient_news_volume_for_shift"}, rationale="insufficient_news_volume_for_shift",
        )

    risk_flags = ("sentiment_shift_detected",) if shift.detected else ()
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL,
        confidence=round(min(1.0, abs(shift.shift)), 4),
        evidence={
            "recent_bullish_share": shift.recent_bullish_share, "baseline_bullish_share": shift.baseline_bullish_share,
            "shift": shift.shift, "recent_count": shift.recent_count, "baseline_count": shift.baseline_count,
        },
        risk_flags=risk_flags,
        rationale=f"sentiment shift={shift.shift} (tone only -- not a directional read)",
    )
