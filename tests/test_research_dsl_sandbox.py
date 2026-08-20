"""Research package structural sandbox proof — "PROMPT 10" §16-21, §57,
§64. Same AST-walk technique as `tests/test_agent_sandbox.py`: this is a
monolith Python process with no OS-level capability sandbox, so "sandbox"
means exactly what `packages/research/dsl.py`'s docstring says it means --
checked on every test run, not a runtime guarantee.

Two independent guarantees proven here:
1. Nothing under packages/research/ (or apps/research_worker/) ever calls
   eval/exec/compile, imports subprocess/os.system-style shells, or
   dynamically imports code -- the DSL tree is the ONLY way an
   experimental strategy's logic reaches this codebase, and it is never
   Python source.
2. "Self-improvement != self-execution" (§57): nothing under
   packages/research/ or apps/research_worker/ imports packages.execution
   or calls a live-order-mutating function -- research can propose; it can
   never place a trade or touch packages.risk's sovereign gate's downstream
   effects directly.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PKG = REPO_ROOT / "packages" / "research"
RESEARCH_WORKER_APP = REPO_ROOT / "apps" / "research_worker"

FORBIDDEN_CALL_NAMES = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_IMPORT_PREFIXES = ("packages.execution", "subprocess", "os.system")
FORBIDDEN_ATTR_CALLS = {("os", "system"), ("os", "popen"), ("subprocess", "run"), ("subprocess", "Popen"), ("subprocess", "call")}


def _python_files():
    files = []
    for pkg in (RESEARCH_PKG, RESEARCH_WORKER_APP):
        files.extend(p for p in pkg.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def test_no_module_ever_calls_eval_exec_compile_or_dunder_import():
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALL_NAMES:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {node.func.id}(...)")
    assert offenders == [], f"eval/exec/compile/__import__ found in research pipeline: {offenders}"


def test_no_module_shells_out_via_os_or_subprocess():
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and (node.func.value.id, node.func.attr) in FORBIDDEN_ATTR_CALLS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {node.func.value.id}.{node.func.attr}(...)")
    assert offenders == [], f"shell-out call found in research pipeline: {offenders}"


def test_dsl_module_itself_never_imports_os_or_subprocess():
    """The DSL evaluator is the single narrowest surface (§16-21) -- it
    should need nothing beyond dataclasses/typing, structurally."""
    tree = ast.parse((RESEARCH_PKG / "dsl.py").read_text())
    banned = {"os", "subprocess", "sys", "importlib", "ctypes", "socket"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders.extend(alias.name for alias in node.names if alias.name.split(".")[0] in banned)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in banned:
            offenders.append(node.module)
    assert offenders == [], f"dsl.py imports a banned module: {offenders}"


def test_no_module_under_packages_research_imports_the_execution_layer():
    offenders = []
    for path in RESEARCH_PKG.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
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
    assert offenders == [], f"packages.execution reached from packages/research/: {offenders}"


def test_no_module_under_research_worker_imports_the_execution_layer():
    offenders = []
    for path in RESEARCH_WORKER_APP.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
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
    assert offenders == [], f"packages.execution reached from apps/research_worker/: {offenders}"


def test_dsl_evaluate_never_receives_a_string_it_would_treat_as_source():
    """Belt-and-suspenders runtime check alongside the static AST proof:
    feeding evaluate_condition a condition tree that contains Python
    source as a string value fails validation (unknown field / unknown
    operator) rather than being executed."""
    from packages.research import dsl

    malicious = {"eq": ["__import__('os').system('echo pwned')", 1]}
    result = dsl.validate(malicious)
    assert result.valid is False
    with pytest.raises(dsl.DslValidationError):
        dsl.evaluate_condition(malicious, {})
