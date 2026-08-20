"""Opportunity Ranking Engine -- "PROMPT 11" §26-29.

Orders opportunities by risk-adjusted attractiveness, not raw return
potential -- reuses packages/quant/scoring's existing `final_score`
(already risk-reward/confidence/drawdown-penalty-adjusted, Phase 2/3) as
the base, and applies only the one thing that's genuinely new here: a
cluster-based penalty from packages/market/clustering.py. An opportunity
that's part of a correlated cluster is a more concentrated, less
diversified bet than its standalone score alone would suggest (§35).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankableOpportunity:
    signal_id: int
    symbol: str
    final_score: float  # packages.quant.scoring's OpportunityScore.final_score
    tier: str  # OpportunityScore.tier
    cluster_ranking_penalty: float = 0.0  # packages.market.clustering's ClusterResult.ranking_penalty, 0.0 if unclustered


@dataclass(frozen=True)
class RankedOpportunity:
    signal_id: int
    symbol: str
    final_score: float
    tier: str
    cluster_ranking_penalty: float
    ranked_score: float
    rank: int


class OpportunityRankingEngine:
    def rank(self, opportunities: list[RankableOpportunity]) -> list[RankedOpportunity]:
        # A cluster penalty discounts final_score PROPORTIONALLY -- e.g. a
        # 0.3 penalty knocks 30% off an otherwise-equal score, rather than
        # a flat point subtraction (which would unfairly punish a
        # low-score opportunity more, in relative terms, than a high-score
        # one carrying the identical penalty).
        scored = [
            (opp, round(opp.final_score * (1.0 - opp.cluster_ranking_penalty), 2)) for opp in opportunities
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [
            RankedOpportunity(
                signal_id=opp.signal_id, symbol=opp.symbol, final_score=opp.final_score, tier=opp.tier,
                cluster_ranking_penalty=opp.cluster_ranking_penalty, ranked_score=ranked_score, rank=i + 1,
            )
            for i, (opp, ranked_score) in enumerate(scored)
        ]
