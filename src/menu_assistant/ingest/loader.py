"""Load and validate a menu from a JSON file."""

from pathlib import Path

from pydantic import ValidationError

from menu_assistant.models import Menu


class MenuLoadError(Exception):
    """Raised when a menu file cannot be read or does not match the menu schema."""


def load_menu(path: Path) -> Menu:
    """Read a JSON menu file and return a validated `Menu`.

    Raises:
        MenuLoadError: if the file is missing, unreadable, not valid JSON,
            or does not satisfy the menu schema and consistency rules.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise MenuLoadError(f"cannot read menu file {path}: {error}") from error

    try:
        return Menu.model_validate_json(raw)
    except ValidationError as error:
        raise MenuLoadError(f"invalid menu file {path}:\n{error}") from error
