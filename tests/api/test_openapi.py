"""The front end's copy of the OpenAPI schema must match the API."""

from pathlib import Path

from menu_assistant.api.openapi import main, schema_json

FRONTEND_SCHEMA = Path(__file__).parents[2] / "frontend" / "openapi.json"


def test_frontend_schema_is_up_to_date() -> None:
    committed = FRONTEND_SCHEMA.read_text(encoding="utf-8")

    assert committed == schema_json(), (
        "frontend/openapi.json is outdated: run `uv run python -m menu_assistant.api.openapi`, "
        "then `pnpm gen:api` in frontend/"
    )


def test_main_writes_the_schema(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"

    assert main([str(path)]) == 0
    assert path.read_text(encoding="utf-8") == schema_json()
