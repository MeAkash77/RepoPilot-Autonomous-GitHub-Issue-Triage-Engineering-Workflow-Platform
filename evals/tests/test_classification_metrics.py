import pytest

from repopilot_evals.classification_metrics import (
    accuracy,
    duplicate_precision_recall,
    macro_f1,
)


def test_accuracy() -> None:
    assert accuracy(["a", "b", "a"], ["a", "b", "b"]) == pytest.approx(2 / 3)


def test_macro_f1_perfect() -> None:
    assert macro_f1(["a", "b"], ["a", "b"]) == 1.0


def test_macro_f1_penalizes_minority_class_failure() -> None:
    # Always predicting the majority class scores high accuracy, low macro F1.
    predicted = ["a"] * 9 + ["a"]
    expected = ["a"] * 9 + ["b"]
    assert accuracy(predicted, expected) == 0.9
    assert macro_f1(predicted, expected) < 0.5


def test_duplicate_precision_recall() -> None:
    precision, recall = duplicate_precision_recall(
        predicted_pairs={(10, 1), (11, 2)}, expected_pairs={(10, 1), (12, 3)}
    )
    assert precision == 0.5
    assert recall == 0.5


def test_duplicate_no_predictions_no_expected_is_perfect() -> None:
    assert duplicate_precision_recall(set(), set()) == (1.0, 1.0)
