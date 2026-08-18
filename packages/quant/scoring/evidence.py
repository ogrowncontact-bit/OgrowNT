"""Structured "why" evidence for an Opportunity — Prompt 3 §23: "Mostrar
apenas justificativas estruturadas", never an LLM's private reasoning. Every
item here is a deterministic read of a number the Scoring Engine already
computed (packages/quant/scoring/inputs.py's ScoringInputs/notes), so the
same Opportunity always produces the same evidence list.
"""
from __future__ import annotations

from dataclasses import dataclass

CONFIRM = "confirm"
WARNING = "warning"

# Component scores are already 0-100; these are the same "clearly good" /
# "clearly bad" bands used nowhere else numerically, just to decide whether
# a component is worth a checkmark or a warning at all -- most components
# near neutral (50) produce neither, since "unremarkable" isn't evidence.
_STRONG = 70.0
_WEAK = 30.0


@dataclass(frozen=True)
class EvidenceItem:
    kind: str  # "confirm" | "warning"
    text: str


def build_evidence(
    *,
    direction: str,
    technical: float,
    pattern: float,
    regime: str,
    regime_fit: float,
    regime_confidence: float,
    historical_edge: float,
    liquidity: float,
    news: float,
    risk_reward: float,
    risk_reward_ratio: float,
    volatility_penalty: float,
    notes: dict,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    pattern_note = notes.get("pattern", {})
    news_note = notes.get("news", {})
    history_note = notes.get("historical_edge", {})

    if technical >= _STRONG:
        items.append(EvidenceItem(CONFIRM, f"Technical setup strong ({direction})"))
    elif technical <= _WEAK:
        items.append(EvidenceItem(WARNING, "Technical setup weak"))

    if pattern_note.get("pattern_detected"):
        pattern_type = str(pattern_note.get("pattern_type", "pattern")).replace("_", " ")
        if pattern_note.get("aligned") is True:
            items.append(EvidenceItem(CONFIRM, f"{pattern_type.title()} pattern confirmed"))
        elif pattern_note.get("aligned") is False:
            items.append(EvidenceItem(WARNING, f"{pattern_type.title()} pattern conflicts with signal direction"))
    else:
        items.append(EvidenceItem(WARNING, "No supporting pattern detected"))

    if regime_fit >= _STRONG:
        items.append(EvidenceItem(CONFIRM, f"Regime compatible ({regime})"))
    elif regime_fit <= _WEAK:
        items.append(EvidenceItem(WARNING, f"Regime unfavorable for this strategy ({regime})"))
    if regime_confidence < 0.5:
        items.append(EvidenceItem(WARNING, "Regime classification itself is low-confidence"))

    if history_note.get("insufficient_history"):
        items.append(EvidenceItem(WARNING, "INSUFFICIENT_HISTORY — historical sample limited"))
    elif historical_edge >= _STRONG:
        items.append(EvidenceItem(CONFIRM, "Historical edge positive in similar conditions"))
    elif historical_edge <= _WEAK:
        items.append(EvidenceItem(WARNING, "Historical edge negative in similar conditions"))

    if risk_reward >= _STRONG:
        items.append(EvidenceItem(CONFIRM, f"Favorable risk/reward ({risk_reward_ratio:.2f})"))
    elif risk_reward <= _WEAK:
        items.append(EvidenceItem(WARNING, f"Risk/reward below target ({risk_reward_ratio:.2f})"))

    if liquidity <= _WEAK:
        items.append(EvidenceItem(WARNING, "Volume below average — liquidity may be thin"))
    elif liquidity >= _STRONG:
        items.append(EvidenceItem(CONFIRM, "Volume increased"))

    if news_note.get("news_count", 0) > 0:
        if news_note.get("aligned") is True:
            items.append(EvidenceItem(CONFIRM, "News sentiment aligned"))
        elif news_note.get("aligned") is False:
            items.append(EvidenceItem(WARNING, "News sentiment conflicts with signal direction"))

    if volatility_penalty > 0:
        items.append(EvidenceItem(WARNING, "Volatility elevated"))

    return items
