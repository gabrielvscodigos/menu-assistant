"""Tests for the evaluation command-line entry point."""

from pathlib import Path

import pytest

from menu_assistant.eval.__main__ import main

DATA_DIR = Path(__file__).parents[2] / "data"


def test_empty_index_exits_with_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MENU_ASSISTANT_CHROMA_PATH", str(tmp_path / "empty-index"))

    exit_code = main(
        [
            "--dataset",
            str(DATA_DIR / "eval" / "retrieval_queries.json"),
            "--menu",
            str(DATA_DIR / "menu.json"),
        ]
    )

    assert exit_code == 1
    assert "is empty" in capsys.readouterr().err
