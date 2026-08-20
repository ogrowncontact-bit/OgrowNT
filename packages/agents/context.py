"""AgentContext — everything a specialist agent is allowed to read.

Built once per (asset, worker cycle) in `packages/agents/orchestrator.py`
and handed to every specialist as the same immutable snapshot, so all 18
agents reason about the same instant instead of racing each other's DB
reads. This mirrors `packages/quant/strategies/base.py::MarketContext` —
deliberately reused here rather than duplicated, since Technical
Analysis/Pattern Hunter/Momentum/Mean Reversion all need exactly what it
already carries (candles, indicators, regime).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from packages.data.quality import QualityReport
from packages.quant.news.context import AssetNewsContext
from packages.quant.strategies.base import MarketContext
from packages.shared.models import Asset, MacroEvent, StrategyRow


@dataclass(frozen=True)
class AgentContext:
    db: Session
    market: MarketContext
    asset: Asset
    now: datetime
    strategy_row: StrategyRow | None = None
    news_context: AssetNewsContext | None = None
    # The already-persisted macro_events table (apps/worker/macro_agent.py's
    # own cadence maintains it) -- read here, never re-fetched from the
    # live provider per asset per cycle, which would be both wasteful and a
    # second source of truth for the same calendar.
    macro_events: tuple[MacroEvent, ...] = ()
    quality_report: QualityReport | None = None
    peer_returns: dict[str, float] = field(default_factory=dict)
