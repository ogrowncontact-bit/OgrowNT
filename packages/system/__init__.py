"""System-level Command Center aggregations — "PROMPT 14" §116-129, §78-93.

health_score.py, diagnostics.py, briefing.py, command_router.py — each a
pure, read-side (or classification-only) function over data other modules
already compute/persist, following the same "no new detection logic, only
new orchestration" discipline this codebase has used since "PROMPT 12"'s
AdvancedRiskEngine. See docs/command-center.md.
"""
