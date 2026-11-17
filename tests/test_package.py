"""Smoke tests for the menu_assistant package layout."""

import importlib
from importlib.metadata import entry_points

import pytest

SUBPACKAGES = ["api", "ingest", "retrieval", "llm", "rag", "eval"]
CONSOLE_SCRIPTS = ["menu-ask", "menu-ingest", "menu-eval", "menu-eval-answers"]


@pytest.mark.parametrize("name", CONSOLE_SCRIPTS)
def test_console_script_points_at_a_main_function(name: str) -> None:
    (script,) = entry_points(group="console_scripts", name=name)

    assert callable(script.load())


def test_package_is_importable() -> None:
    package = importlib.import_module("menu_assistant")

    assert package.__doc__


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_is_importable(name: str) -> None:
    module = importlib.import_module(f"menu_assistant.{name}")

    assert module.__doc__
