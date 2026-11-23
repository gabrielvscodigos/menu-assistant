"""Tests for settings that affect index compatibility."""

from menu_assistant.config import INDEX_FORMAT_VERSION, Settings


def test_index_signature_depends_on_model_document_prefix_and_format_only() -> None:
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


def test_index_signature_includes_the_data_format_version() -> None:
    assert Settings().index_signature.endswith(f"|format={INDEX_FORMAT_VERSION}")
