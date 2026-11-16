"""Tests for settings that affect index compatibility."""

from menu_assistant.config import Settings


def test_index_signature_depends_on_model_and_document_prefix_only() -> None:
    base = Settings(embedding_model="m", embedding_document_prefix="passage: ")

    assert base.index_signature != Settings(embedding_model="other").index_signature
    assert (
        base.index_signature
        != base.model_copy(update={"embedding_document_prefix": ""}).index_signature
    )
    assert (
        base.index_signature
        == base.model_copy(update={"embedding_query_prefix": "q"}).index_signature
    )
    assert base.index_signature == base.model_copy(update={"tag_boost": 1.0}).index_signature
