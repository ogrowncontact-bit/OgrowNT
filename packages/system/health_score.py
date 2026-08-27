"""System Health Score + Trading Readiness — "PROMPT 14" §116-119.

Reuses GET /api/system/health's existing green/yellow/red component checks
(apps/api/routers/system.py) rather than a second, competing health engine —
this module adds the one thing that endpoint never computed: a single 0-100
number and a READY/CAUTION/DEGRADED/NOT_READY/HALTED readiness state, both
pure functions of that SAME component map plus SystemState.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.shared.models import SystemState

READY = "ready"
CAUTION = "caution"
DEGRADED = "degraded"
NOT_READY = "not_ready"
HALTED = "halted"

READINESS_STATES = (READY, CAUTION, DEGRADED, NOT_READY, HALTED)

# Weights sum to 1.0 — same "documented assumption, not a fitted model"
# convention as packages/quant/learning/strategy_stats.py's _HEALTH_WEIGHTS
# and packages/risk/advanced_engine.py's risk_score blend.
_WEIGHTS: dict[str, float] = {
    "database": 0.25,
    "worker": 0.25,
    "market_data": 0.15,
    "risk_engine": 0.15,
    "trading_state": 0.10,
    "ai_services": 0.10,
}
_STATUS_SCORE = {"green": 100.0, "yellow": 60.0, "red": 0.0}


@dataclass(frozen=True)
class SystemHealthScore:
    score: float  # 0-100
    readiness_state: str
    components: dict[str, float] = field(default_factory=dict)  # component -> 0-100
    reasons: list[str] = field(default_factory=list)


def _trading_state_score(state: SystemState | None) -> tuple[float, list[str]]:
    if state is None:
        return 100.0, []
    reasons: list[str] = []
    if not state.trading_enabled:
        reasons.append("kill switch is triggered")
        return 0.0, reasons
    if state.trading_paused:
        reasons.append(f"trading paused: {state.paused_reason or 'no reason recorded'}")
        return 40.0, reasons
    if state.safety_belt_level in ("emergency", "kill_switch"):
        reasons.append(f"safety belt at {state.safety_belt_level}")
        return 10.0, reasons
    if state.safety_belt_level == "defensive":
        return 55.0, reasons
    if state.safety_belt_level == "caution":
        return 75.0, reasons
    return 100.0, reasons


def compute_system_health_score(db: Session, *, component_health: dict[str, str]) -> SystemHealthScore:
    """`component_health` is name->status ('green'/'yellow'/'red'/'yellow'),
    the SAME dict GET /api/system/health already computes — passed in
    rather than recomputed, so this stays a pure aggregation over data
    another endpoint already derives (packages/analytics/overview.py's own
    precedent for "read-side over data another module writes")."""
    reasons: list[str] = []
    sub_scores: dict[str, float] = {}
    for name, status in component_health.items():
        sub_scores[name] = _STATUS_SCORE.get(status, 50.0)
        if status == "red":
            reasons.append(f"{name} is unhealthy")
        elif status == "yellow":
            reasons.append(f"{name} is degraded")

    state = db.get(SystemState, True)
    trading_score, trading_reasons = _trading_state_score(state)
    sub_scores["trading_state"] = trading_score
    reasons.extend(trading_reasons)

    total_weight = sum(_WEIGHTS.get(name, 0.0) for name in sub_scores) or 1.0
    weighted = sum(_WEIGHTS.get(name, 0.0) * value for name, value in sub_scores.items())
    score = round(weighted / total_weight, 1)

    readiness = _readiness_state(score=score, component_health=component_health, state=state)
    return SystemHealthScore(score=score, readiness_state=readiness, components=sub_scores, reasons=reasons)


def _readiness_state(*, score: float, component_health: dict[str, str], state: SystemState | None) -> str:
    # §119: "não significa autorização de live trading... indica: o sistema
    # está operacional para paper/sandbox?" — HALTED is reserved for the
    # two facts that make paper trading itself unsafe right now (DB down,
    # or the Kill Switch already tripped), never a live-trading concept.
    if component_health.get("database") == "red":
        return HALTED
    if state is not None and not state.trading_enabled:
        return HALTED
    if score < 40:
        return NOT_READY
    if score < 60:
        return DEGRADED
    if score < 85:
        return CAUTION
    # trading_state's own weight (10%) is too small for a deliberate pause to
    # ever drag the weighted score below 85 on its own -- an operator-visible
    # pause must never still read as unqualified READY.
    if state is not None and state.trading_paused:
        return CAUTION
    return READY
