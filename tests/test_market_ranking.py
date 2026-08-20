"""Opportunity Ranking Engine -- "PROMPT 11" §26-29."""
from __future__ import annotations

from packages.market.ranking import OpportunityRankingEngine, RankableOpportunity


def test_rank_orders_by_ranked_score_descending():
    opportunities = [
        RankableOpportunity(signal_id=1, symbol="A", final_score=60.0, tier="watch"),
        RankableOpportunity(signal_id=2, symbol="B", final_score=90.0, tier="exceptional"),
        RankableOpportunity(signal_id=3, symbol="C", final_score=75.0, tier="high_quality"),
    ]
    ranked = OpportunityRankingEngine().rank(opportunities)
    assert [r.symbol for r in ranked] == ["B", "C", "A"]
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_rank_applies_proportional_cluster_penalty():
    clustered = RankableOpportunity(signal_id=1, symbol="CLUSTERED", final_score=90.0, tier="exceptional", cluster_ranking_penalty=0.5)
    standalone = RankableOpportunity(signal_id=2, symbol="STANDALONE", final_score=80.0, tier="high_quality", cluster_ranking_penalty=0.0)

    ranked = OpportunityRankingEngine().rank([clustered, standalone])
    # 90 * (1 - 0.5) = 45 < 80 -- the standalone opportunity should now rank first
    # even though its raw final_score was lower.
    assert ranked[0].symbol == "STANDALONE"
    assert ranked[1].symbol == "CLUSTERED"
    assert ranked[1].ranked_score == 45.0


def test_rank_with_no_cluster_penalty_preserves_final_score_order():
    a = RankableOpportunity(signal_id=1, symbol="A", final_score=70.0, tier="high_quality")
    b = RankableOpportunity(signal_id=2, symbol="B", final_score=50.0, tier="watch")
    ranked = OpportunityRankingEngine().rank([a, b])
    assert ranked[0].ranked_score == 70.0
    assert ranked[1].ranked_score == 50.0


def test_rank_empty_list_returns_empty():
    assert OpportunityRankingEngine().rank([]) == []


def test_rank_handles_tied_scores_without_crashing():
    a = RankableOpportunity(signal_id=1, symbol="A", final_score=60.0, tier="watch")
    b = RankableOpportunity(signal_id=2, symbol="B", final_score=60.0, tier="watch")
    ranked = OpportunityRankingEngine().rank([a, b])
    assert {r.symbol for r in ranked} == {"A", "B"}
    assert [r.rank for r in ranked] == [1, 2]
