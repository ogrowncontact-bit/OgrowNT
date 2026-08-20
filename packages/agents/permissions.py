"""Per-agent tool/data permission table — "PROMPT 9" §11-14, §60-63.

This is a single monolith Python process with no OS-level capability
sandbox, so "sandbox" here means two concrete, checked things rather than
a process-isolation guarantee:

1. A declarative table (below) of which read-only package each specialist
   is expected to depend on — reviewable at a glance, and asserted against
   each module's actual imports by `test_every_specialist_only_imports_its_
   declared_permissions` in `tests/test_agent_sandbox.py`.
2. A structural AST proof that NO module under `packages/agents/` imports
   `packages.execution` or calls `open_position`/`close_position`/
   `reduce_position` anywhere — `tests/test_agent_sandbox.py`'s
   `test_no_specialist_can_reach_the_execution_layer`, the same AST-walk
   technique already used by `tests/test_critical_safety_battery.py`'s
   `test_open_position_is_never_called_outside_the_risk_gated_path`.

Both are real and enforced on every test run; neither is a runtime
capability check inside the process itself. Documented as such rather than
oversold as a true sandbox.
"""
from __future__ import annotations

# agent_code -> package prefixes this agent's specialist module may import
# from, beyond stdlib, packages.agents.* itself, and packages.shared.models
# (every agent may read ORM row shapes; only these are its *analysis*
# dependencies).
PERMISSIONS: dict[str, tuple[str, ...]] = {
    "chief_quant": ("packages.quant.strategies", "packages.quant.regime"),
    "technical_analysis": ("packages.quant.indicators",),
    "pattern_hunter": ("packages.quant.patterns",),
    "market_regime": ("packages.quant.regime",),
    "momentum": ("packages.quant.strategies",),
    "mean_reversion": ("packages.quant.strategies",),
    "macro": ("packages.data.connectors.macro",),
    "news_intelligence": ("packages.quant.news",),
    "sentiment": ("packages.quant.news",),
    "quant_research": ("packages.quant.learning",),
    "portfolio_intelligence": ("packages.portfolio", "packages.risk.config"),
    "risk_guardian": ("packages.risk", "packages.portfolio"),
    "execution_intelligence": ("packages.shared.models",),
    "learning": ("packages.quant.learning", "packages.risk.strategy_health"),
    "anomaly_detection": ("packages.quant.patterns",),
    "data_quality": ("packages.data.quality",),
    "strategy_health": ("packages.risk.strategy_health", "packages.quant.learning"),
    "emergency_guardian": ("packages.risk.safety_belt", "packages.risk.config", "packages.portfolio"),
}

# The one boundary that must never be crossed by ANY agent, regardless of
# its permission row above.
FORBIDDEN_IMPORT_PREFIXES = ("packages.execution",)
FORBIDDEN_CALL_NAMES = ("open_position", "close_position", "reduce_position")

ALWAYS_ALLOWED_PREFIXES = (
    "packages.agents", "packages.shared.models", "packages.shared.market_data", "packages.data.connectors.market",
)
