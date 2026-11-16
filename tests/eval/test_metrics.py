"""Tests for the ranking metrics."""

import pytest

from menu_assistant.eval.metrics import mean, recall_at_k, reciprocal_rank


def test_recall_counts_relevant_items_within_k() -> None:
    assert recall_at_k(["a", "x", "b", "c"], {"a", "b", "c"}, k=3) == pytest.approx(2 / 3)


def test_recall_is_capped_when_more_relevant_than_k() -> None:
    assert recall_at_k(["a", "b"], {"a", "b", "c", "d"}, k=2) == 0.5


def test_recall_rejects_empty_relevant_set() -> None:
    with pytest.raises(ValueError):
        recall_at_k(["a"], set(), k=1)


@pytest.mark.parametrize(
    ("retrieved", "expected"),
    [(["a", "b"], 1.0), (["x", "a"], 0.5), (["x", "y", "b"], 1 / 3), (["x"], 0.0), ([], 0.0)],
)
def test_reciprocal_rank_uses_first_relevant_item(retrieved: list[str], expected: float) -> None:
    assert reciprocal_rank(retrieved, {"a", "b"}) == pytest.approx(expected)


def test_mean_of_empty_sequence_is_zero() -> None:
    assert mean([]) == 0.0
    assert mean([1.0, 0.0]) == 0.5
