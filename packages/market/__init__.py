"""Global Market Intelligence & 24/7 Opportunity Discovery -- "PROMPT 11".

See docs/global-market-intelligence.md for the full design writeup. This
package is read-only with respect to trading: every module here produces
MARKET INFORMATION, OPPORTUNITIES, or ALERTS -- never an order. The
scanner NEVER executes a trade ("PROMPT 11" §95); packages.risk /
packages.execution remain the only sovereign paths to a real (paper) fill,
exactly as before this package existed.

An Opportunity Score is NOT a probability -- see
packages/shared/models.py::OpportunityScore.confidence and
packages/market/ranking.py's module docstring for where that distinction
is enforced.
"""
