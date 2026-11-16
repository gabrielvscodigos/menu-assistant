"""Metadata keys shared by indexing (writes them) and retrieval (filters on them)."""

from menu_assistant.models import Allergen, DietaryFlag

COURSE_KEY = "course"
NAME_KEY = "name"
DISH_JSON_KEY = "dish_json"


def allergen_key(allergen: Allergen) -> str:
    """Metadata key holding whether a dish contains `allergen`."""
    return f"allergen_{allergen.value}"


def diet_key(flag: DietaryFlag) -> str:
    """Metadata key holding whether a dish carries the dietary `flag`."""
    return f"diet_{flag.value}"
