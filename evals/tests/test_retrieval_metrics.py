from repopilot_evals.retrieval_metrics import LabeledQuery, mean_recall_at_k, recall_at_k


def test_recall_at_k_full_hit() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "b"}, k=3) == 1.0


def test_recall_at_k_partial() -> None:
    assert recall_at_k(["a", "x", "y"], {"a", "b"}, k=3) == 0.5


def test_recall_at_k_respects_cutoff() -> None:
    assert recall_at_k(["x", "y", "a"], {"a"}, k=2) == 0.0


def test_mean_recall() -> None:
    results = [
        (LabeledQuery("q1", {"a"}), ["a", "b"]),
        (LabeledQuery("q2", {"c"}), ["x", "y"]),
    ]
    assert mean_recall_at_k(results, k=2) == 0.5
