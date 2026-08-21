from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session, require_admin_role
from apps.api.risk_view import derive_decision_view
from apps.api.schemas import (
    AdvancedRiskOut,
    CircuitBreakerOut,
    ConcentrationClusterOut,
    ConcentrationOut,
    ConfigDiffOut,
    KillSwitchStateOut,
    PortfolioStressTestOut,
    RecoveryReadinessOut,
    RiskCheckOut,
    RiskConfigVersionOut,
    RiskDecisionOut,
    RiskStateOut,
)
from packages.portfolio.state import compute_state
from packages.risk import circuit_breakers as cb
from packages.risk import config_version as cv
from packages.risk.advanced_engine import assess_portfolio_risk
from packages.risk.concentration import assess_concentration
from packages.risk.config import load_risk_limits
from packages.risk.stress import compute_value_at_risk, run_live_stress_test
from packages.shared.models import AdminUser, Asset, RiskCheck, RiskDecision, Signal, StrategyRow, SystemState

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("", response_model=RiskStateOut)
def get_risk_state(
    limit: int = 20, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> RiskStateOut:
    system_state = db.get(SystemState, True)
    limits = load_risk_limits()

    rows = db.execute(
        select(RiskDecision, Signal, Asset, StrategyRow)
        .join(Signal, Signal.id == RiskDecision.signal_id)
        .join(Asset, Asset.id == Signal.asset_id)
        .join(StrategyRow, StrategyRow.id == Signal.strategy_id)
        .order_by(RiskDecision.created_at.desc())
        .limit(limit)
    ).all()

    decisions = []
    for decision, signal, asset, strategy in rows:
        checks = db.query(RiskCheck).filter(RiskCheck.signal_id == signal.id).order_by(RiskCheck.id).all()
        view = derive_decision_view(
            approved=decision.approved, reason=decision.reason, approved_size=decision.approved_size,
            checks=checks, signal=signal,
        )
        decisions.append(
            RiskDecisionOut(
                signal_id=signal.id, asset_symbol=asset.symbol, strategy_code=strategy.code,
                approved=decision.approved, approved_size=decision.approved_size, reason=decision.reason,
                safety_belt_level=decision.safety_belt_level, created_at=decision.created_at,
                checks=[RiskCheckOut(check_name=c.check_name, passed=c.passed, detail=c.detail) for c in checks],
                **view,
            )
        )

    return RiskStateOut(
        safety_belt_level=system_state.safety_belt_level if system_state else "normal",
        trading_enabled=system_state.trading_enabled if system_state else True,
        limits={
            "capital": asdict(limits.capital),
            "per_trade": asdict(limits.per_trade),
            "portfolio": asdict(limits.portfolio),
            "loss_limits": asdict(limits.loss_limits),
            "liquidity": asdict(limits.liquidity),
            "data_quality": asdict(limits.data_quality),
            "safety_belt_multipliers": asdict(limits.safety_belt_multipliers),
            "news_risk_multipliers": asdict(limits.news_risk_multipliers),
            "drawdown_levels": {
                "level_1": asdict(limits.drawdown_levels.level_1), "level_2": asdict(limits.drawdown_levels.level_2),
                "level_3": asdict(limits.drawdown_levels.level_3), "level_4": asdict(limits.drawdown_levels.level_4),
                "level_5": asdict(limits.drawdown_levels.level_5),
            },
            "recovery": asdict(limits.recovery),
        },
        recent_decisions=decisions,
    )


# -- "PROMPT 12" Advanced Risk & Capital Defense Engine ---------------------


@router.get("/advanced", response_model=AdvancedRiskOut)
def get_advanced_risk(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> AdvancedRiskOut:
    """The AdvancedRiskEngine's current portfolio-wide RiskScore/RiskState
    (packages/risk/advanced_engine.py) -- computed fresh on every call, the
    same "cheap to recompute, no staleness risk" choice packages/data/
    quality.py's compute_quality_score already makes; apps/worker/
    capital_defense.py separately persists a RiskAssessment row on its own
    cadence for history (see GET /api/risk/config-versions for the
    unrelated config-audit history)."""
    limits = load_risk_limits()
    assessment = assess_portfolio_risk(db, limits)
    return AdvancedRiskOut(
        ts=assessment.ts, risk_score=assessment.risk_score, risk_state=assessment.risk_state,
        capital_preservation_mode=assessment.capital_preservation_mode, zero_trade_mode=assessment.zero_trade_mode,
        degraded=assessment.degraded, reasons=assessment.reasons,
        equity=assessment.capital_state.equity if assessment.capital_state else None,
        drawdown_pct=assessment.drawdown.drawdown_pct if assessment.drawdown else None,
        peak_equity=assessment.capital_state.peak_equity if assessment.capital_state else None,
        drawdown_state=assessment.drawdown.risk_state if assessment.drawdown else None,
        drawdown_level=assessment.drawdown.level if assessment.drawdown else None,
        concentration_state=assessment.concentration.concentration_state if assessment.concentration else None,
        system_risk_state=assessment.system_risk.state if assessment.system_risk else None,
        execution_risk_state=assessment.execution_risk.state if assessment.execution_risk else None,
        model_risk_state=assessment.model_risk.state if assessment.model_risk else None,
        data_risk_state=assessment.data_risk.state if assessment.data_risk else None,
    )


@router.get("/breakers", response_model=list[CircuitBreakerOut])
def get_circuit_breakers(
    strategy_id: int | None = None, asset_id: int | None = None,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[CircuitBreakerOut]:
    """The 6 named circuit breakers ("PROMPT 12" §63-69). The 4 portfolio-
    wide ones (system/portfolio/execution/data) are always included;
    strategy/asset are per-entity and only included when their id is
    given -- there is no single "the" strategy or asset to check otherwise.
    """
    statuses = cb.portfolio_wide_breaker_statuses(db)
    if strategy_id is not None:
        statuses.append(cb.strategy_breaker_status(db, strategy_id))
    if asset_id is not None:
        statuses.append(cb.asset_breaker_status(db, asset_id))
    return [CircuitBreakerOut(name=s.name, tripped=s.tripped, reason=s.reason, scope_id=s.scope_id) for s in statuses]


@router.get("/concentration", response_model=ConcentrationOut)
def get_concentration(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> ConcentrationOut:
    limits = load_risk_limits()
    equity = compute_state(db).equity
    assessment = assess_concentration(db, limits, equity)
    return ConcentrationOut(
        open_position_count=assessment.open_position_count, total_exposure_notional=assessment.total_exposure_notional,
        max_cluster_exposure_pct=assessment.max_cluster_exposure_pct, concentration_state=assessment.concentration_state,
        asset_class_exposure_pct=assessment.asset_class_exposure_pct, hidden_factor_warnings=assessment.hidden_factor_warnings,
        clusters=[
            ConcentrationClusterOut(
                symbols=list(c.symbols), direction=c.direction, factor=c.factor,
                avg_correlation=c.avg_correlation, ranking_penalty=c.ranking_penalty,
            )
            for c in assessment.clusters
        ],
    )


@router.get("/stress", response_model=PortfolioStressTestOut)
def get_stress_test(
    method: str = "bootstrap", num_simulations: int = 1000, random_seed: int = 42,
    drawdown_threshold_pct: float | None = None, capital_loss_threshold_pct: float | None = None,
    var_confidence: float = 0.95,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> PortfolioStressTestOut:
    """Live-portfolio Monte Carlo / Risk of Ruin (packages/risk/stress.py,
    reusing "PROMPT 7"'s backtest bootstrap-resampling engine) plus
    historical-simulation VaR/CVaR -- "PROMPT 12" §77-84's explicit "never
    the sole metric" instruction is why this endpoint always returns both
    families together rather than as separate calls."""
    limits = load_risk_limits()
    stress = run_live_stress_test(
        db, initial_capital=limits.capital.initial_paper_capital, method=method, num_simulations=num_simulations,
        random_seed=random_seed, drawdown_threshold_pct=drawdown_threshold_pct,
        capital_loss_threshold_pct=capital_loss_threshold_pct,
    )
    var = compute_value_at_risk(db, confidence=var_confidence)
    return PortfolioStressTestOut(
        trades_used=stress.trades_used, sufficient_history=stress.sufficient_history,
        monte_carlo=asdict(stress.monte_carlo) if stress.monte_carlo else None,
        risk_of_ruin=asdict(stress.risk_of_ruin) if stress.risk_of_ruin else None,
        var_pct=var.var_pct, cvar_pct=var.cvar_pct, var_confidence=var.confidence, var_num_returns=var.num_returns,
        var_note=var.note,
    )


@router.get("/kill-switch/state", response_model=KillSwitchStateOut)
def get_kill_switch_state(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> KillSwitchStateOut:
    state = db.get(SystemState, True)
    return KillSwitchStateOut(
        kill_switch_state=state.kill_switch_state if state else cb.ARMED,
        recovery_mode=state.recovery_mode if state else False,
        trading_enabled=state.trading_enabled if state else True,
    )


@router.post("/kill-switch/recovery/start", response_model=KillSwitchStateOut)
def start_kill_switch_recovery(
    db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role),
) -> KillSwitchStateOut:
    """"PROMPT 12" §61: only an admin (this single-tenant system's
    equivalent of "SUPER_ADMIN" -- see packages/shared/models.py's
    AdminUser docstring) may begin recovery. No AI/agent/strategy code path
    in this repository calls packages/risk/circuit_breakers.py's
    start_recovery -- grep the codebase to verify."""
    try:
        state = cb.start_recovery(db, actor=admin.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KillSwitchStateOut(
        kill_switch_state=state.kill_switch_state, recovery_mode=state.recovery_mode, trading_enabled=state.trading_enabled,
    )


@router.get("/kill-switch/recovery/readiness", response_model=RecoveryReadinessOut)
def get_kill_switch_recovery_readiness(
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> RecoveryReadinessOut:
    readiness = cb.check_recovery_readiness(db)
    return RecoveryReadinessOut(ready=readiness.ready, reasons=readiness.reasons)


@router.post("/kill-switch/recovery/confirm", response_model=KillSwitchStateOut)
def confirm_kill_switch_recovery(
    force: bool = False, db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role),
) -> KillSwitchStateOut:
    """Requires check_recovery_readiness() to report ready unless
    force=True -- an explicit, itself-audited admin override (§62: "recovery
    deve exigir: system health, risk review, manual confirmation" -- force
    is the manual confirmation overriding an automated readiness signal a
    human has reviewed and judges safe, never a way to skip the review
    itself, which already ran and is recorded either way)."""
    try:
        state = cb.confirm_recovery(db, actor=admin.email, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KillSwitchStateOut(
        kill_switch_state=state.kill_switch_state, recovery_mode=state.recovery_mode, trading_enabled=state.trading_enabled,
    )


@router.get("/config-versions", response_model=list[RiskConfigVersionOut])
def list_risk_config_versions(
    limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[RiskConfigVersionOut]:
    versions = cv.list_versions(db, limit=limit)
    return [
        RiskConfigVersionOut(
            version=v.version, created_at=v.created_at, approved_by=v.approved_by, reason=v.reason,
            status=v.status, parameters=v.parameters,
        )
        for v in versions
    ]


@router.get("/config-versions/{version}", response_model=RiskConfigVersionOut)
def get_risk_config_version(
    version: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> RiskConfigVersionOut:
    row = cv.get_version(db, version)
    if row is None:
        raise HTTPException(status_code=404, detail=f"risk config version {version} not found")
    return RiskConfigVersionOut(
        version=row.version, created_at=row.created_at, approved_by=row.approved_by, reason=row.reason,
        status=row.status, parameters=row.parameters,
    )


@router.get("/config-versions/diff/{from_version}/{to_version}", response_model=list[ConfigDiffOut])
def diff_risk_config_versions(
    from_version: int, to_version: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[ConfigDiffOut]:
    old = cv.get_version(db, from_version)
    new = cv.get_version(db, to_version)
    if old is None:
        raise HTTPException(status_code=404, detail=f"risk config version {from_version} not found")
    if new is None:
        raise HTTPException(status_code=404, detail=f"risk config version {to_version} not found")
    diffs = cv.diff_versions(old.parameters, new.parameters)
    return [ConfigDiffOut(key=d.key, old_value=d.old_value, new_value=d.new_value) for d in diffs]
