"""Autonomous Research & Evolution Engine — "PROMPT 10".

See docs/autonomous-research.md for the full design writeup. Nothing in
this package ever executes a trade, writes to a live strategy's
production parameters, or bypasses admin approval — packages.risk /
packages.execution / packages.quant.learning.promotion remain the only
sovereign paths to, respectively, a real order and a capital-tier
promotion, exactly as before this package existed. Self-improvement here
means "the system can research and PROPOSE a better strategy version," not
"the system can apply one" (Prompt 10 §1: "SELF-IMPROVEMENT != SELF-
EXECUTION").
"""
