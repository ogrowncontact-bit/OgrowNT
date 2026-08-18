from packages.quant.scoring.evidence import build_evidence


def _kwargs(**overrides):
    base = dict(
        direction="long", technical=50.0, pattern=50.0, regime="trending_bull", regime_fit=50.0,
        regime_confidence=0.8, historical_edge=50.0, liquidity=50.0, news=50.0, risk_reward=50.0,
        risk_reward_ratio=2.0, volatility_penalty=0.0,
        notes={"pattern": {"pattern_detected": False}, "news": {"news_count": 0},
               "historical_edge": {"insufficient_history": False}},
    )
    base.update(overrides)
    return base


def test_neutral_everything_produces_minimal_evidence():
    # Every component at exactly neutral (50) shouldn't manufacture
    # confirms or warnings out of "unremarkable".
    items = build_evidence(**_kwargs())
    assert not any("Technical" in i.text for i in items)
    assert not any("Regime compatible" in i.text or "unfavorable" in i.text for i in items)


def test_strong_technical_is_a_confirm():
    items = build_evidence(**_kwargs(technical=85.0))
    confirms = [i for i in items if i.kind == "confirm"]
    assert any("Technical setup strong" in i.text for i in confirms)


def test_weak_technical_is_a_warning():
    items = build_evidence(**_kwargs(technical=10.0))
    warnings = [i for i in items if i.kind == "warning"]
    assert any("Technical setup weak" in i.text for i in warnings)


def test_aligned_pattern_is_a_confirm_with_pattern_type():
    items = build_evidence(**_kwargs(notes={
        "pattern": {"pattern_detected": True, "pattern_type": "breakout", "aligned": True},
        "news": {"news_count": 0}, "historical_edge": {"insufficient_history": False},
    }))
    confirms = [i.text for i in items if i.kind == "confirm"]
    assert any("Breakout" in t and "confirmed" in t for t in confirms)


def test_conflicting_pattern_is_a_warning():
    items = build_evidence(**_kwargs(notes={
        "pattern": {"pattern_detected": True, "pattern_type": "reversal", "aligned": False},
        "news": {"news_count": 0}, "historical_edge": {"insufficient_history": False},
    }))
    warnings = [i.text for i in items if i.kind == "warning"]
    assert any("conflicts" in t for t in warnings)


def test_no_pattern_detected_is_a_warning():
    items = build_evidence(**_kwargs())
    warnings = [i.text for i in items if i.kind == "warning"]
    assert any("No supporting pattern detected" in t for t in warnings)


def test_regime_compatible_is_a_confirm():
    items = build_evidence(**_kwargs(regime_fit=90.0, regime="trending_bull"))
    confirms = [i.text for i in items if i.kind == "confirm"]
    assert any("Regime compatible" in t and "trending_bull" in t for t in confirms)


def test_regime_unfavorable_is_a_warning():
    items = build_evidence(**_kwargs(regime_fit=5.0))
    warnings = [i.text for i in items if i.kind == "warning"]
    assert any("Regime unfavorable" in t for t in warnings)


def test_low_regime_confidence_adds_its_own_warning():
    items = build_evidence(**_kwargs(regime_confidence=0.2))
    warnings = [i.text for i in items if i.kind == "warning"]
    assert any("low-confidence" in t for t in warnings)


def test_insufficient_history_is_a_warning_with_the_exact_flag_name():
    items = build_evidence(**_kwargs(notes={
        "pattern": {"pattern_detected": False}, "news": {"news_count": 0},
        "historical_edge": {"insufficient_history": True},
    }))
    warnings = [i.text for i in items if i.kind == "warning"]
    assert any("INSUFFICIENT_HISTORY" in t for t in warnings)


def test_strong_historical_edge_is_a_confirm_when_history_exists():
    items = build_evidence(**_kwargs(historical_edge=85.0, notes={
        "pattern": {"pattern_detected": False}, "news": {"news_count": 0},
        "historical_edge": {"insufficient_history": False},
    }))
    confirms = [i.text for i in items if i.kind == "confirm"]
    assert any("Historical edge positive" in t for t in confirms)


def test_favorable_risk_reward_is_a_confirm_with_ratio():
    items = build_evidence(**_kwargs(risk_reward=90.0, risk_reward_ratio=3.5))
    confirms = [i.text for i in items if i.kind == "confirm"]
    assert any("Favorable risk/reward" in t and "3.50" in t for t in confirms)


def test_poor_risk_reward_is_a_warning():
    items = build_evidence(**_kwargs(risk_reward=5.0, risk_reward_ratio=0.4))
    warnings = [i.text for i in items if i.kind == "warning"]
    assert any("Risk/reward below target" in t for t in warnings)


def test_low_liquidity_is_a_warning():
    items = build_evidence(**_kwargs(liquidity=10.0))
    warnings = [i.text for i in items if i.kind == "warning"]
    assert any("Volume below average" in t for t in warnings)


def test_high_liquidity_is_a_confirm():
    items = build_evidence(**_kwargs(liquidity=90.0))
    confirms = [i.text for i in items if i.kind == "confirm"]
    assert any("Volume increased" in t for t in confirms)


def test_aligned_news_is_a_confirm():
    items = build_evidence(**_kwargs(notes={
        "pattern": {"pattern_detected": False}, "news": {"news_count": 2, "aligned": True},
        "historical_edge": {"insufficient_history": False},
    }))
    confirms = [i.text for i in items if i.kind == "confirm"]
    assert any("News sentiment aligned" in t for t in confirms)


def test_conflicting_news_is_a_warning():
    items = build_evidence(**_kwargs(notes={
        "pattern": {"pattern_detected": False}, "news": {"news_count": 2, "aligned": False},
        "historical_edge": {"insufficient_history": False},
    }))
    warnings = [i.text for i in items if i.kind == "warning"]
    assert any("News sentiment conflicts" in t for t in warnings)


def test_volatility_penalty_is_a_warning():
    items = build_evidence(**_kwargs(volatility_penalty=8.0))
    warnings = [i.text for i in items if i.kind == "warning"]
    assert any("Volatility elevated" in t for t in warnings)


def test_no_volatility_penalty_no_warning():
    items = build_evidence(**_kwargs(volatility_penalty=0.0))
    assert not any("Volatility elevated" in i.text for i in items)
