"""Tests for opening the persistent collection and guarding against model mismatches."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from menu_assistant.retrieval.vector_store import IndexMismatchError, open_collection


def add_one(path: Path, signature: str) -> None:
    collection = open_collection(path, "dishes", signature)
    embeddings: list[Sequence[float]] = [[1.0, 0.0]]
    collection.upsert(ids=["a"], embeddings=embeddings)


def test_reopening_with_same_signature_keeps_data(tmp_path: Path) -> None:
    add_one(tmp_path, "model-a")

    assert open_collection(tmp_path, "dishes", "model-a").count() == 1


def test_different_signature_is_rejected_by_default(tmp_path: Path) -> None:
    add_one(tmp_path, "model-a")

    with pytest.raises(IndexMismatchError, match="re-run ingestion"):
        open_collection(tmp_path, "dishes", "model-b")


def test_different_signature_resets_when_allowed(tmp_path: Path) -> None:
    add_one(tmp_path, "model-a")

    collection = open_collection(tmp_path, "dishes", "model-b", reset_on_mismatch=True)

    assert collection.count() == 0
    assert open_collection(tmp_path, "dishes", "model-b").count() == 0
