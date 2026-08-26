"""Retrieval quality metrics.

recall@k over a labeled query set: fraction of queries where at least the
expected fraction of labeled-relevant documents appear in the top k. The
full Langfuse-integrated harness lands in Phase 5; these pure functions
are its building blocks and power the Phase 2 mini-eval.
"""

from dataclasses import dataclass


@dataclass
class LabeledQuery:
    query: str
    relevant_refs: set[str]  # document source_refs judged relevant


def recall_at_k(retrieved_refs: list[str], relevant_refs: set[str], k: int) -> float:
    """Fraction of relevant docs present in the top-k retrieved refs."""
    if not relevant_refs:
        return 0.0
    top = set(retrieved_refs[:k])
    return len(top & relevant_refs) / len(relevant_refs)


def mean_recall_at_k(results: list[tuple[LabeledQuery, list[str]]], k: int) -> float:
    """Average recall@k across (labeled query, retrieved refs) pairs."""
    if not results:
        return 0.0
    return sum(
        recall_at_k(retrieved, labeled.relevant_refs, k) for labeled, retrieved in results
    ) / len(results)
