"""Export the API's OpenAPI schema: `python -m menu_assistant.api.openapi [path]`.

The front end generates its TypeScript types from this file (`frontend/openapi.json`),
and a test fails when the committed file no longer matches the API, so the two cannot
drift apart silently. Writing the schema needs no index, model, or LLM.
"""

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from menu_assistant.api.main import app

DEFAULT_PATH = Path("frontend/openapi.json")


def schema_json() -> str:
    """The OpenAPI schema as stable, pretty-printed JSON."""
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    path = Path(args[0]) if args else DEFAULT_PATH
    path.write_text(schema_json(), encoding="utf-8", newline="\n")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
