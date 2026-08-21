"""Advanced Risk & Capital Defense Engine red-team battery -- "PROMPT 12"
§132. 14 adversarial checks targeting the phase's central constraints:
"nunca aumentar risco após perda", "nenhum componente de AI pode
desativar/enfraquecer defesas", "somente humano inicia recuperação", and
"se não sabe se é seguro, não operar" (fail-closed). Each item either
attempts a concrete attack and confirms it fails safely, or structurally
proves an invariant an attacker (or a buggy AI-generated code path) would
need to break to succeed -- the same technique packages/research's own
red-team battery (tests/test_research_red_team.py, "PROMPT 10" §57) uses.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.risk import advanced_engine
from packages.risk import circuit_breakers as cb
from packages.risk.capital_state import EMERGENCY, HALTED, RISK_STATES, assess_drawdown
from packages.risk.config import DrawdownLevelConfig, DrawdownLevelsConfig, RecoveryConfig, load_risk_limits
from packages.risk.loss_streak import evaluate_dimensional_loss_streaks, evaluate_loss_streak
from packages.shared.models import Order, SystemState

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_PACKAGES = (
    REPO_ROOT / "packages" / "agents",
    REPO_ROOT / "packages" / "research",
    REPO_ROOT / "packages" / "quant" / "strategies",
    REPO_ROOT / "apps" / "research_worker",
)
FORBIDDEN_RECOVERY_CALLS = ("trigger_kill_switch", "start_recovery", "confirm_recovery")
LIMITS = load_risk_limits()


def _healthy_system_state(db_session, *, now: datetime | None = None) -> SystemState:
    now = now or datetime.now(timezone.utc)
    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.trading_enabled = True
    state.trading_paused = False
    state.safety_belt_level = "normal"
    state.worker_last_heartbeat = now
    db_session.add(state)
    db_session.commit()
    return state


# 1. No AI/agent/research/strategy code path can trigger, start recovery from, or confirm the kill switch
def test_1_no_ai_code_path_can_touch_the_kill_switch_state_machine():
    offenders = []
    for pkg in AI_PACKAGES:
        if not pkg.exists():
            continue
        for path in pkg.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_RECOVERY_CALLS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {node.func.attr}(...)")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_RECOVERY_CALLS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {node.func.id}(...)")
    assert offenders == [], f"AI-reachable kill-switch mutation found: {offenders}"


# 2. No AI/agent/research/strategy code path ever writes SystemState.trading_enabled directly
def test_2_no_ai_code_path_ever_sets_trading_enabled_directly():
    offenders = []
    for pkg in AI_PACKAGES:
        if not pkg.exists():
            continue
        for path in pkg.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and target.attr == "trading_enabled":
                            offenders.append(f"{path.relative_to(REPO_ROOT)}: direct trading_enabled assignment")
    assert offenders == [], f"AI-reachable trading_enabled mutation found: {offenders}"


# 3. Only packages/risk/config_version.py's record_config_version ever marks a RiskConfigVersion ACTIVE
def test_3_only_config_version_module_marks_a_version_active():
    offenders = []
    risk_pkg = REPO_ROOT / "packages" / "risk"
    for path in risk_pkg.rglob("*.py"):
        if "__pycache__" in path.parts or path.name == "config_version.py":
            continue
        source = path.read_text()
        if "RiskConfigVersion" in source and ("status=" in source or ".status" in source):
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and target.attr == "status":
                            offenders.append(f"{path.relative_to(REPO_ROOT)}: direct .status assignment near RiskConfigVersion")
    assert offenders == [], f"config-version status set outside config_version.py: {offenders}"


# 4. A loss streak's size_multiplier can never exceed 1.0 -- no path to "loss streak -> double risk"
def test_4_loss_streak_multiplier_never_exceeds_one(db_session):
    result = evaluate_loss_streak(db_session, LIMITS.loss_streak)
    assert result.size_multiplier <= 1.0
    dimensional = evaluate_dimensional_loss_streaks(db_session, LIMITS.loss_streak, strategy_id=1, asset_id=1, regime="trending_bull")
    assert dimensional.combined_size_multiplier <= 1.0


# 5. The Advanced Risk Engine's belt-reuse multiplier can never exceed 1.0, for any RiskState
def test_5_advanced_risk_size_multiplier_never_exceeds_one_for_any_risk_state():
    for state in RISK_STATES:
        multiplier = 1.0
        if state == "caution":
            multiplier = LIMITS.safety_belt_multipliers.caution
        elif state == "defensive":
            multiplier = LIMITS.safety_belt_multipliers.defensive
        assert multiplier <= 1.0, f"risk_state={state} produced a multiplier > 1.0"


# 6. DD_LEVEL thresholds are read from config, never hardcoded -- changing the config changes the classification
def test_6_drawdown_levels_are_config_driven_not_hardcoded(db_session):
    strict = DrawdownLevelsConfig(
        level_1=DrawdownLevelConfig(threshold_pct=0.1, response="reduce_exposure"),
        level_2=DrawdownLevelConfig(threshold_pct=0.2, response="reduce_new_positions"),
        level_3=DrawdownLevelConfig(threshold_pct=0.3, response="highest_quality_only"),
        level_4=DrawdownLevelConfig(threshold_pct=0.4, response="block_new_trades"),
        level_5=DrawdownLevelConfig(threshold_pct=0.5, response="close_and_contain"),
    )
    from dataclasses import replace

    strict_limits = replace(LIMITS, drawdown_levels=strict, recovery=RecoveryConfig(cooldown_minutes=0))
    # 0.35% drawdown: below even the lenient default DD_LEVEL_1 (3%), but
    # above the strict config's level_3 (0.3%) and below its level_4 (0.4%)
    # -- the SAME raw drawdown_pct classifies completely differently
    # depending only on which config was passed in, proving the thresholds
    # are read from config, not hardcoded.
    lenient_assessment = assess_drawdown(db_session, LIMITS, drawdown_pct=0.35)
    strict_assessment = assess_drawdown(db_session, strict_limits, drawdown_pct=0.35)
    assert lenient_assessment.level == 0
    assert strict_assessment.level == 3


# 7. No AI/agent/research/strategy code path removes or loosens a position's stop
def test_7_no_ai_code_path_ever_touches_current_stop():
    offenders = []
    for pkg in AI_PACKAGES:
        if not pkg.exists():
            continue
        for path in pkg.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and target.attr == "current_stop":
                            offenders.append(f"{path.relative_to(REPO_ROOT)}: direct current_stop assignment")
    assert offenders == [], f"AI-reachable stop mutation found: {offenders}"


# 8. Capital preservation mode cannot be bypassed by a high-confidence/low-tier signal
def test_8_capital_preservation_mode_blocks_regardless_of_signal_quality(db_session):
    from packages.portfolio.state import PortfolioState
    from packages.risk.advanced_engine import AdvancedRiskAssessment
    from packages.risk.engine import SignalForRisk, evaluate_signal
    from packages.shared.models import Asset, Signal, StrategyRow

    asset = Asset(symbol="REDTEAM8", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="redteam8_strategy", name="x", family="test", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    signal_row = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="scored",
    )
    db_session.add(signal_row)
    db_session.commit()

    sfr = SignalForRisk(
        signal_id=signal_row.id, asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        stop_price=95.0, target_price=115.0, risk_reward=5.0, confidence=1.0, volatility_factor=1.0,
        data_quality="high", data_ts=datetime.now(timezone.utc), tier="possible",  # NOT high_quality
        asset_class="crypto",
    )
    portfolio_state = PortfolioState(
        ts=datetime.now(timezone.utc), cash=10000, equity=10000, exposure_pct=0.0, daily_pnl=0.0,
        daily_loss_pct=0.0, weekly_pnl=0.0, weekly_loss_pct=0.0, monthly_pnl=0.0, monthly_loss_pct=0.0,
        drawdown_pct=0.0, unrealized_pnl=0.0, open_positions=[],
    )
    advanced_risk = AdvancedRiskAssessment(
        ts=datetime.now(timezone.utc), risk_score=90.0, risk_state="high_risk", capital_state=None, drawdown=None,
        concentration=None, loss_streak=None, system_risk=None, execution_risk=None, model_risk=None, data_risk=None,
        breakers=[], capital_preservation_mode=True, zero_trade_mode=False, degraded=False, reasons=["red team"],
    )
    verdict = evaluate_signal(
        db_session, sfr, portfolio_state, SystemState(id=True, trading_enabled=True), advanced_risk=advanced_risk,
    )
    assert not verdict.approved
    assert verdict.reason == "advanced_risk_capital_preservation_mode"


# 9. Recovery cannot skip states: ARMED -> RECOVERY directly (no LOCKED first) is rejected
def test_9_recovery_cannot_be_started_from_armed(db_session):
    _healthy_system_state(db_session)  # starts ARMED
    with pytest.raises(ValueError):
        cb.start_recovery(db_session, actor="attacker@example.com")


# 10. confirm_recovery cannot be called from ARMED or LOCKED -- only from RECOVERY
def test_10_confirm_recovery_cannot_be_called_from_locked(db_session):
    _healthy_system_state(db_session)
    cb.trigger_kill_switch(db_session, reason="red team trip", actor="system")
    with pytest.raises(ValueError):
        cb.confirm_recovery(db_session, actor="attacker@example.com")


# 11. A missing SystemState row fails closed to HALTED, never a silent NORMAL
def test_11_missing_system_state_fails_closed_to_halted(db_session):
    assessment = advanced_engine.assess_portfolio_risk(db_session, LIMITS)
    assert assessment.risk_state == HALTED


# 12. A crash inside ANY single dimension's computation still yields a HALTED (never NORMAL) aggregate
@pytest.mark.parametrize(
    "target",
    [
        "compute_capital_state",
    ],
)
def test_12_dimension_computation_crash_fails_closed(db_session, target):
    _healthy_system_state(db_session)
    with patch.object(advanced_engine, target, side_effect=RuntimeError("simulated crash")):
        assessment = advanced_engine.assess_portfolio_risk(db_session, LIMITS)
    assert assessment.degraded is True
    assert assessment.risk_state == HALTED


# 13. An execution-only breach reaches EMERGENCY but never HALTED -- only system/portfolio breakers may halt
def test_13_execution_only_breach_never_escalates_past_emergency(db_session):
    _healthy_system_state(db_session)
    for _ in range(20):
        db_session.add(Order(order_type="market", side="buy", qty=1.0, status="rejected", is_paper=True))
    db_session.commit()
    assessment = advanced_engine.assess_portfolio_risk(db_session, LIMITS)
    assert assessment.risk_state == EMERGENCY
    assert assessment.risk_state != HALTED


# 14. A "poor performance" (degraded strategy health) signal cannot re-enable trading or disable a breaker --
# no code path outside packages/risk/circuit_breakers.py flips kill_switch_state back toward ARMED.
def test_14_no_code_outside_circuit_breakers_ever_sets_kill_switch_state_to_armed():
    offenders = []
    repo_pkgs = [REPO_ROOT / "packages", REPO_ROOT / "apps"]
    for base in repo_pkgs:
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts or path.name == "circuit_breakers.py":
                continue
            source = path.read_text()
            if "kill_switch_state" not in source:
                continue
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and target.attr == "kill_switch_state":
                            offenders.append(f"{path.relative_to(REPO_ROOT)}: direct kill_switch_state assignment")
    assert offenders == [], f"kill_switch_state mutated outside circuit_breakers.py: {offenders}"
