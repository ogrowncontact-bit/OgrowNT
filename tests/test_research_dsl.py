"""Strategy DSL — "PROMPT 10" §16-21, §64. Correctness of the whitelisted
condition/expression tree: validation, evaluation, and every rejection
path a malformed or malicious definition could take.
"""
from __future__ import annotations

import pytest

from packages.research import dsl


def test_valid_condition_validates_and_evaluates_true():
    condition = {"and": [{"gt": ["rsi_14", 70]}, {"eq": ["regime", {"lit": "trending_bull"}]}]}
    result = dsl.validate(condition)
    assert result.valid is True
    assert dsl.evaluate_condition(condition, {"rsi_14": 75, "regime": "trending_bull"}) is True


def test_valid_condition_evaluates_false_when_a_clause_fails():
    condition = {"and": [{"gt": ["rsi_14", 70]}, {"eq": ["regime", {"lit": "trending_bull"}]}]}
    assert dsl.evaluate_condition(condition, {"rsi_14": 40, "regime": "trending_bull"}) is False


def test_or_not_composition():
    condition = {"or": [{"lt": ["rsi_14", 30]}, {"not": {"eq": ["regime", {"lit": "ranging"}]}}]}
    assert dsl.evaluate_condition(condition, {"rsi_14": 50, "regime": "trending_bull"}) is True
    assert dsl.evaluate_condition(condition, {"rsi_14": 50, "regime": "ranging"}) is False


def test_arithmetic_expression_evaluates():
    expression = {"add": [{"mul": ["atr_14", 2]}, "close"]}
    value = dsl.evaluate_expression(expression, {"atr_14": 1.5, "close": 100.0})
    assert value == pytest.approx(103.0)


@pytest.mark.parametrize(
    "field",
    ["__import__", "os", "eval", "close.__class__", "not_a_real_field", "regime; import os"],
)
def test_unwhitelisted_field_reference_fails_validation(field):
    condition = {"gt": [field, 1]}
    result = dsl.validate(condition)
    assert result.valid is False
    assert result.errors


def test_unknown_operator_fails_validation():
    condition = {"exec": ["print('hi')"]}
    result = dsl.validate(condition)
    assert result.valid is False


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        [],
        "just a string",  # not a field on ALLOWED_FIELDS
        {"and": "not a list"},
        {},
        {"gt": 1, "lt": 2},  # two keys -- not a single-operator node
    ],
)
def test_malformed_tree_fails_validation_not_an_exception(malformed):
    result = dsl.validate(malformed)
    assert result.valid is False
    assert result.errors


@pytest.mark.parametrize(
    "condition",
    [
        {"gt": ["rsi_14"]},  # too few operands
        {"gt": ["rsi_14", 1, 2]},  # too many operands
        {"not": [{"gt": ["rsi_14", 1]}, {"gt": ["rsi_14", 2]}]},  # 'not' takes exactly one
        {"and": []},  # empty variadic op
    ],
)
def test_wrong_arity_fails_validation(condition):
    result = dsl.validate(condition)
    assert result.valid is False
    assert result.errors


def test_literal_wrapper_compares_against_a_categorical_field():
    condition = {"eq": ["regime", {"lit": "trending_bull"}]}
    assert dsl.validate(condition).valid is True
    assert dsl.evaluate_condition(condition, {"regime": "trending_bull"}) is True
    assert dsl.evaluate_condition(condition, {"regime": "ranging"}) is False


def test_evaluate_condition_raises_on_invalid_tree_rather_than_silently_passing():
    with pytest.raises(dsl.DslValidationError):
        dsl.evaluate_condition({"gt": ["not_a_real_field", 1]}, {"not_a_real_field": 999})


_CATEGORICAL_FIELDS = {"regime", "pattern_direction"}


def test_all_allowed_fields_are_actually_resolvable_from_a_full_context():
    context = {field: 1.0 for field in dsl.ALLOWED_FIELDS if field not in _CATEGORICAL_FIELDS}
    context["regime"] = "trending_bull"
    context["pattern_direction"] = "bullish"
    for field in dsl.ALLOWED_FIELDS:
        if field in _CATEGORICAL_FIELDS:
            condition = {"eq": [field, {"lit": context[field]}]}
        else:
            condition = {"gte": [field, 0]}
        assert dsl.validate(condition).valid is True
        dsl.evaluate_condition(condition, context)  # must not raise
