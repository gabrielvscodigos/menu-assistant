"""Smoke tests for the menu_assistant package layout."""

import importlib

import pytest

SUBPACKAGES = ["api", "ingest", "retrieval", "llm", "rag", "eval"]


def test_package_is_importable() -> None:
    package = importlib.import_module("menu_assistant")

    assert package.__doc__


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_is_importable(name: str) -> None:
    module = importlib.import_module(f"menu_assistant.{name}")

    assert module.__doc__
