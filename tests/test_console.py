"""Tests for console output helpers."""

import io
import sys

import pytest

from menu_assistant.console import use_utf8_output


def test_redirected_legacy_output_is_switched_to_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer = io.BytesIO()
    legacy = io.TextIOWrapper(buffer, encoding="cp1252", newline="\n")
    monkeypatch.setattr(sys, "stdout", legacy)

    use_utf8_output()
    print("Olá, açaí → ok")
    legacy.flush()

    assert buffer.getvalue().decode("utf-8") == "Olá, açaí → ok\n"


def test_streams_that_are_not_text_wrappers_are_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    use_utf8_output()

    assert sys.stdout is stream
