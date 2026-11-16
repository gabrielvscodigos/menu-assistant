"""Tests for the ingestion command-line entry point."""

from pathlib import Path

import pytest

from menu_assistant.ingest.__main__ import main


def test_invalid_menu_exits_with_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(tmp_path / "missing.json")])

    assert exit_code == 1
    assert "error: cannot read menu file" in capsys.readouterr().err
