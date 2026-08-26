from repopilot_retrieval.fusion import reciprocal_rank_fusion


def test_item_in_both_rankings_beats_single_ranking_items() -> None:
    fused = reciprocal_rank_fusion([[1, 2, 3], [2, 4, 5]])
    assert fused[0][0] == 2


def test_scores_match_formula() -> None:
    fused = dict(reciprocal_rank_fusion([[10], [10]], k=60))
    assert abs(fused[10] - 2 / 61) < 1e-12


def test_deterministic_tie_break_by_id() -> None:
    fused = reciprocal_rank_fusion([[5], [3]])
    assert [item for item, _ in fused] == [3, 5]


def test_empty_rankings() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
