"""Reciprocal Rank Fusion.

RRF(d) = sum over rankings r of 1 / (k + rank_r(d)). k=60 per the original
Cormack et al. paper; it damps the head so one ranking can't dominate.
"""

from collections.abc import Sequence

RRF_K = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[int]], k: int = RRF_K
) -> list[tuple[int, float]]:
    """Fuse rankings (lists of item ids, best first) → (id, score) best first.

    Ties break by id for determinism.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
