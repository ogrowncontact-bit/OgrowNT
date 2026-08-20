"""Registry of all 18 specialist agents — "PROMPT 9" §1.

`SPECIALIST_REGISTRY` is the single source of truth `AgentOrchestrator`
(`packages/agents/orchestrator.py`), the `/api/agents` router, and the
dashboard AI Command Center all read from — adding a 19th agent means
adding one entry here, never touching the orchestrator's loop.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage
from packages.agents.specialists import (
    anomaly_detection,
    chief_quant,
    data_quality,
    emergency_guardian,
    execution_intelligence,
    learning,
    macro,
    market_regime,
    mean_reversion,
    momentum,
    news_intelligence,
    pattern_hunter,
    portfolio_intelligence,
    quant_research,
    risk_guardian,
    sentiment,
    strategy_health,
    technical_analysis,
)

AnalyzeFn = Callable[[AgentContext], AgentMessage]


@dataclass(frozen=True)
class SpecialistMeta:
    code: str
    name: str
    directional: bool  # True: casts a real long/short/neutral vote counted by ConsensusEngine. False: context/guardian-only.
    analyze: AnalyzeFn


SPECIALIST_REGISTRY: dict[str, SpecialistMeta] = {
    meta.code: meta
    for meta in [
        SpecialistMeta("chief_quant", "Chief Quant", True, chief_quant.analyze),
        SpecialistMeta("technical_analysis", "Technical Analysis", True, technical_analysis.analyze),
        SpecialistMeta("pattern_hunter", "Pattern Hunter", True, pattern_hunter.analyze),
        SpecialistMeta("market_regime", "Market Regime", True, market_regime.analyze),
        SpecialistMeta("momentum", "Momentum", True, momentum.analyze),
        SpecialistMeta("mean_reversion", "Mean Reversion", True, mean_reversion.analyze),
        SpecialistMeta("macro", "Macro", False, macro.analyze),
        SpecialistMeta("news_intelligence", "News Intelligence", True, news_intelligence.analyze),
        SpecialistMeta("sentiment", "Sentiment", False, sentiment.analyze),
        SpecialistMeta("quant_research", "Quant Research", False, quant_research.analyze),
        SpecialistMeta("portfolio_intelligence", "Portfolio Intelligence", False, portfolio_intelligence.analyze),
        SpecialistMeta("risk_guardian", "Risk Guardian", False, risk_guardian.analyze),
        SpecialistMeta("execution_intelligence", "Execution Intelligence", False, execution_intelligence.analyze),
        SpecialistMeta("learning", "Learning", False, learning.analyze),
        SpecialistMeta("anomaly_detection", "Anomaly Detection", False, anomaly_detection.analyze),
        SpecialistMeta("data_quality", "Data Quality", False, data_quality.analyze),
        SpecialistMeta("strategy_health", "Strategy Health", False, strategy_health.analyze),
        SpecialistMeta("emergency_guardian", "Emergency Guardian", False, emergency_guardian.analyze),
    ]
}

assert len(SPECIALIST_REGISTRY) == 18, "PROMPT 9 §1 requires exactly 18 named specialist agents"
