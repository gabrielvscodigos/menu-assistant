"""Ranking metrics for retrieval evaluation. All functions are pure."""

from collections.abc import Sequence, Set


def recall_at_k(retrieved: Sequence[str], relevant: Set[str], k: int) -> float:
    """Fraction of relevant items that appear in the top `k` retrieved items.

    When there are more relevant items than `k`, the best possible score is
    `k / len(relevant)`, which keeps the metric honest about what was missed.
    """
    if not relevant:
        raise ValueError("relevant must not be empty")
    hits = len(set(retrieved[:k]) & relevant)
    return hits / len(relevant)


def reciprocal_rank(retrieved: Sequence[str], relevant: Set[str]) -> float:
    """1 / rank of the first relevant item (1-based), or 0.0 if none was retrieved."""
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean, defined as 0.0 for an empty sequence."""
    return sum(values) / len(values) if values else 0.0
