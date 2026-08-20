"""Safe Strategy DSL — "PROMPT 10" §27-28.

A small, whitelisted, dict-based condition/expression tree — NEVER Python
source, never passed to `eval`/`exec`/`compile` anywhere in this module
(structurally proven: `tests/test_research_dsl_sandbox.py` AST-walks this
file the same way `tests/test_agent_sandbox.py` proves the multi-agent
layer never reaches `packages.execution`). An experimental strategy's
entry/exit logic is one of these trees, evaluated against a flat context
of already-computed indicator/regime/pattern values — it can only ever
read numbers/strings that were already produced by the trusted, existing
pipeline (`packages.quant.indicators`/`regime`/`patterns`), never run
arbitrary code, reach a filesystem, or import anything.

Example (§27):

    ENTRY = {"and": [{"gt": ["rsi_14", 70]}, {"eq": ["regime", {"lit": "trending_bull"}]}]}
    STOP  = {"sub": ["close", {"mul": ["atr_14", 2]}]}   # entry - ATR*2

Every bare string anywhere in a tree is a FIELD reference, checked against
ALLOWED_FIELDS -- deliberately unambiguous (no guessing whether a typo'd
field name was "really" meant as a literal). A string constant to compare
a categorical field (regime/pattern_direction) against must be wrapped
explicitly: {"lit": "trending_bull"}.
"""
from __future__ import annotations

from dataclasses import dataclass

# Every field a condition/expression is allowed to reference — the
# complete list of what packages.quant.indicators.core.IndicatorSet and
# packages.quant.regime.classifier.RegimeResult already compute, plus the
# constant "close" alias. Anything not in this set is a ValueError, not a
# silent None -- an experimental strategy referencing a typo'd field must
# fail loudly at validation time, not quietly misprice a stop.
ALLOWED_FIELDS = frozenset({
    "close", "sma_fast", "sma_slow", "ema_fast", "ema_slow", "rsi_14", "atr_14",
    "realized_vol_20", "trend_strength", "roc_10", "avg_volume_20", "recent_high_20",
    "recent_low_20", "regime", "regime_confidence", "pattern_direction", "pattern_strength",
})

_BOOL_OPS = {"and", "or", "not"}
_COMPARISON_OPS = {"gt", "gte", "lt", "lte", "eq", "ne"}
_ARITHMETIC_OPS = {"add", "sub", "mul", "div"}
_LITERAL_OP = "lit"
# Fixed-arity operators -- "not" plus every comparison/arithmetic op take
# exactly this many operands. "and"/"or" are checked separately (>= 1,
# variable arity, not in this table).
_FIXED_ARITY = {"not": 1, **{op: 2 for op in _COMPARISON_OPS | _ARITHMETIC_OPS}}


class DslValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()


def validate(node) -> ValidationResult:
    """Checks every field reference in `node` is in ALLOWED_FIELDS and
    every operator is one of the closed set this module implements --
    called once when a StrategyVersion's dsl_definition is first created
    (packages/research/generator.py), so a bad reference fails at
    authoring time, not mid-experiment."""
    errors: list[str] = []
    _validate_recursive(node, errors)
    return ValidationResult(valid=not errors, errors=tuple(errors))


def _validate_recursive(node, errors: list[str]) -> None:
    if isinstance(node, (int, float, bool)):
        return
    if isinstance(node, str):
        if node not in ALLOWED_FIELDS:
            errors.append(f"unknown field reference: {node!r}")
        return
    if not isinstance(node, dict) or len(node) != 1:
        errors.append(f"malformed DSL node: {node!r}")
        return
    (op, args), = node.items()
    if op == _LITERAL_OP:
        if not isinstance(args, (int, float, bool, str)):
            errors.append(f"malformed literal: {args!r}")
        return
    if op not in _BOOL_OPS | _COMPARISON_OPS | _ARITHMETIC_OPS:
        errors.append(f"unknown operator: {op!r}")
        return
    args_list = args if isinstance(args, list) else [args]
    if op in ("and", "or"):
        if not args_list:
            errors.append(f"{op!r} requires at least one operand")
    elif op in _FIXED_ARITY and len(args_list) != _FIXED_ARITY[op]:
        errors.append(f"{op!r} requires exactly {_FIXED_ARITY[op]} operand(s), got {len(args_list)}")
    for arg in args_list:
        _validate_recursive(arg, errors)


def _resolve(node, context: dict[str, float | str]):
    if isinstance(node, (int, float, bool)):
        return node
    if isinstance(node, str):
        if node not in ALLOWED_FIELDS:
            raise DslValidationError(f"unknown field reference: {node!r}")
        if node not in context:
            raise DslValidationError(f"field {node!r} has no value in this context")
        return context[node]
    if not isinstance(node, dict) or len(node) != 1:
        raise DslValidationError(f"malformed DSL node: {node!r}")
    (op, args), = node.items()
    if op == _LITERAL_OP:
        if not isinstance(args, (int, float, bool, str)):
            raise DslValidationError(f"malformed literal: {args!r}")
        return args
    args_list = args if isinstance(args, list) else [args]
    if op in ("and", "or"):
        if not args_list:
            raise DslValidationError(f"{op!r} requires at least one operand")
    elif op in _FIXED_ARITY and len(args_list) != _FIXED_ARITY[op]:
        raise DslValidationError(f"{op!r} requires exactly {_FIXED_ARITY[op]} operand(s), got {len(args_list)}")

    if op == "not":
        return not evaluate_condition(args_list[0], context)
    if op == "and":
        return all(evaluate_condition(a, context) for a in args_list)
    if op == "or":
        return any(evaluate_condition(a, context) for a in args_list)
    if op in _COMPARISON_OPS:
        left, right = _resolve(args_list[0], context), _resolve(args_list[1], context)
        if left is None or right is None:
            return False  # missing data -> honestly "condition not met", never a guess
        return {"gt": left > right, "gte": left >= right, "lt": left < right, "lte": left <= right,
                "eq": left == right, "ne": left != right}[op]
    if op in _ARITHMETIC_OPS:
        left, right = _resolve(args_list[0], context), _resolve(args_list[1], context)
        if left is None or right is None:
            return None
        if op == "div" and right == 0:
            return None  # honest "undefined", never a fabricated division-by-zero result
        return {"add": left + right, "sub": left - right, "mul": left * right, "div": left / right}[op]
    raise DslValidationError(f"unknown operator: {op!r}")


def evaluate_condition(node, context: dict[str, float | str]) -> bool:
    result = _resolve(node, context)
    return bool(result) if result is not None else False


def evaluate_expression(node, context: dict[str, float | str]) -> float | None:
    result = _resolve(node, context)
    if isinstance(result, bool):
        raise DslValidationError("a boolean condition was used where a numeric expression was expected")
    return result
