"""Classification metrics: accuracy and macro-F1, dependency-free."""

from collections import Counter


def accuracy(predicted: list[str], expected: list[str]) -> float:
    if not expected:
        return 0.0
    hits = sum(1 for p, e in zip(predicted, expected, strict=True) if p == e)
    return hits / len(expected)


def macro_f1(predicted: list[str], expected: list[str]) -> float:
    """Unweighted mean of per-class F1 over classes present in expected."""
    if not expected:
        return 0.0
    classes = sorted(set(expected))
    f1_scores = []
    for cls in classes:
        tp = sum(1 for p, e in zip(predicted, expected, strict=True) if p == cls and e == cls)
        fp = sum(1 for p, e in zip(predicted, expected, strict=True) if p == cls and e != cls)
        fn = sum(1 for p, e in zip(predicted, expected, strict=True) if p != cls and e == cls)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_scores.append(f1)
    return sum(f1_scores) / len(f1_scores)


def duplicate_precision_recall(
    predicted_pairs: set[tuple[int, int]], expected_pairs: set[tuple[int, int]]
) -> tuple[float, float]:
    """Pairs are (new_issue, duplicate_of), order-normalized by caller."""
    if not predicted_pairs:
        return (0.0 if expected_pairs else 1.0, 0.0 if expected_pairs else 1.0)
    tp = len(predicted_pairs & expected_pairs)
    precision = tp / len(predicted_pairs)
    recall = tp / len(expected_pairs) if expected_pairs else 1.0
    return precision, recall


def class_distribution(labels: list[str]) -> dict[str, int]:
    return dict(Counter(labels))
