"""ResearchHypothesis engine — "PROMPT 10" §3-4, §11-15, §41."""
from __future__ import annotations

import pytest

from packages.research.hypothesis import (
    TRIGGER_STRATEGY_DEGRADATION,
    assess_quality,
    compute_priority_score,
    create_hypothesis,
    find_similar_recent_hypothesis,
)
from packages.shared.models import ResearchHypothesis


def test_create_hypothesis_persists_a_det_grounded_row(db_session):
    hyp = create_hypothesis(
        db_session, trigger=TRIGGER_STRATEGY_DEGRADATION, problem="strategy:momentum_v1",
        observation="health score dropped below quarantine threshold", evidence={"health_score": 30.0},
    )
    assert hyp is not None
    assert hyp.status == "proposed"
    assert hyp.source == TRIGGER_STRATEGY_DEGRADATION
    assert "momentum_v1" in hyp.description or "strategy:momentum_v1" in hyp.description
    assert 0.0 <= hyp.priority_score <= 100.0
    reloaded = db_session.get(ResearchHypothesis, hyp.id)
    assert reloaded is not None


def test_unknown_trigger_raises(db_session):
    with pytest.raises(ValueError):
        create_hypothesis(db_session, trigger="not_a_real_trigger", problem="x", observation="x", evidence={})


def test_unknown_risk_or_complexity_raises(db_session):
    with pytest.raises(ValueError):
        create_hypothesis(
            db_session, trigger=TRIGGER_STRATEGY_DEGRADATION, problem="x", observation="x", evidence={}, risk="extreme",
        )
    with pytest.raises(ValueError):
        create_hypothesis(
            db_session, trigger=TRIGGER_STRATEGY_DEGRADATION, problem="x", observation="x", evidence={}, complexity="extreme",
        )


def test_similar_recent_hypothesis_is_not_duplicated(db_session):
    first = create_hypothesis(
        db_session, trigger=TRIGGER_STRATEGY_DEGRADATION, problem="strategy:trend_following_v1",
        observation="obs", evidence={"x": 1},
    )
    assert first is not None
    second = create_hypothesis(
        db_session, trigger=TRIGGER_STRATEGY_DEGRADATION, problem="strategy:trend_following_v1",
        observation="a different observation", evidence={"x": 2},
    )
    assert second is None  # deduped, not a second row


def test_different_problem_is_not_deduped(db_session):
    create_hypothesis(
        db_session, trigger=TRIGGER_STRATEGY_DEGRADATION, problem="strategy:mean_reversion_v1",
        observation="obs", evidence={},
    )
    other = create_hypothesis(
        db_session, trigger=TRIGGER_STRATEGY_DEGRADATION, problem="strategy:momentum_v1",
        observation="obs", evidence={},
    )
    assert other is not None


def test_find_similar_recent_hypothesis_respects_cooldown_window(db_session):
    from datetime import datetime, timedelta, timezone

    old = ResearchHypothesis(
        title="old", description="old", problem="strategy:old_one", observation="obs", hypothesis="h",
        expected_effect="e", source=TRIGGER_STRATEGY_DEGRADATION, status="proposed",
    )
    db_session.add(old)
    db_session.commit()
    old.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    db_session.commit()

    found = find_similar_recent_hypothesis(db_session, source=TRIGGER_STRATEGY_DEGRADATION, problem="strategy:old_one", cooldown_days=14)
    assert found is None  # outside the 14-day cooldown -- allowed to re-propose


def test_compute_priority_score_rewards_novel_testable_evidence():
    quality = assess_quality(hypothesis_text="a" * 30, expected_effect="b" * 20, assets=["BTCUSDT"], is_novel=True, complexity="low")
    high = compute_priority_score(quality=quality, evidence_strength=1.0, risk="low", complexity="low")

    low_quality = assess_quality(hypothesis_text="", expected_effect="", assets=[], is_novel=False, complexity="high")
    low = compute_priority_score(quality=low_quality, evidence_strength=0.0, risk="high", complexity="high")

    assert high > low
    assert 0.0 <= high <= 100.0
    assert 0.0 <= low <= 100.0


def test_llm_client_none_never_blocks_hypothesis_creation(db_session):
    """No ANTHROPIC_API_KEY configured in the test environment -- creation
    must still succeed via the DET-only fallback (llm_client=None is the
    default)."""
    hyp = create_hypothesis(
        db_session, trigger="manual", problem="det-only:no-llm-check", observation="obs", evidence={"note": "det-only"},
    )
    assert hyp is not None
    assert hyp.hypothesis  # non-empty DET narrative
