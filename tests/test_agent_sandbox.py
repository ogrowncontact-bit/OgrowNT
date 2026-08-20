"""Agent sandbox / permission table — "PROMPT 9" §11-14, §60-63.

Structural, AST-based proof (same technique as
tests/test_critical_safety_battery.py::test_open_position_is_never_called_
outside_the_risk_gated_path and tests/test_backtest_lab_full_simulation.py's
test_no_live_trading_anywhere_in_the_lab_pipeline): this is a monolith
Python process with no OS-level capability sandbox, so "sandbox" here means
exactly what packages/agents/permissions.py's docstring says it means --
checked on every test run, not a runtime guarantee.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from packages.agents.permissions import FORBIDDEN_CALL_NAMES, FORBIDDEN_IMPORT_PREFIXES, PERMISSIONS
from packages.agents.specialists import SPECIALIST_REGISTRY

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_PKG = REPO_ROOT / "packages" / "agents"


def _agent_files():
    return [p for p in AGENTS_PKG.rglob("*.py") if "__pycache__" not in p.parts]


def test_no_module_under_packages_agents_imports_the_execution_layer():
    offenders = []
    for path in _agent_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name == prefix or alias.name.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: import {alias.name}")
                continue
            if module and any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: from {module} import ...")

    assert offenders == [], f"packages.execution reached from packages/agents/: {offenders}"


def test_no_module_under_packages_agents_calls_a_real_order_mutating_function():
    offenders = []
    for path in _agent_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALL_NAMES:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {node.func.id}(...)")

    assert offenders == [], f"order-mutating call found under packages/agents/: {offenders}"


def test_permission_table_covers_every_registered_specialist():
    assert set(PERMISSIONS.keys()) == set(SPECIALIST_REGISTRY.keys())


@pytest.mark.parametrize("agent_code", sorted(SPECIALIST_REGISTRY.keys()))
def test_every_specialist_module_stays_within_its_declared_permissions(agent_code):
    """Each specialist's own module may only import from its declared
    permission row (plus stdlib, packages.agents.* itself, and the always-
    allowed shared-read prefixes) -- not a proof against a determined
    developer editing the file, but a real, automatically re-checked
    boundary the same way every other structural test in this suite is."""
    from packages.agents.permissions import ALWAYS_ALLOWED_PREFIXES

    path = AGENTS_PKG / "specialists" / f"{agent_code}.py"
    allowed = PERMISSIONS[agent_code] + ALWAYS_ALLOWED_PREFIXES
    tree = ast.parse(path.read_text())
    offenders = []
    for node in ast.walk(tree):
        module = None
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("packages."):
            module = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("packages."):
                    module = alias.name
        if module is None:
            continue
        if not any(module == prefix or module.startswith(prefix + ".") for prefix in allowed):
            offenders.append(module)

    assert offenders == [], f"{agent_code} imports outside its declared permissions: {offenders}"
