"""Console helpers shared by the command-line entry points."""

import io
import sys


def use_utf8_output() -> None:
    """Write CLI output as UTF-8.

    When output is piped or redirected on Windows, Python falls back to the legacy code
    page (cp1252), which garbles Portuguese answers ("Olá" -> "Ol�") and fails outright on
    characters outside it. Interactive consoles already use UTF-8, so this is a no-op
    there.
    """
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper) and stream.encoding.lower() != "utf-8":
            stream.reconfigure(encoding="utf-8")
