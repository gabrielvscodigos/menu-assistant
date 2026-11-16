"""Convert dishes into the text and metadata stored in the vector index.

Each dish becomes exactly one document (no further chunking): dishes are short, and
one document per dish keeps retrieval results and citations one-to-one with the menu.
"""

from menu_assistant.models import Allergen, DietaryFlag, Dish

ALLERGEN_KEY_PREFIX = "allergen_"
DIET_KEY_PREFIX = "diet_"
DISH_JSON_KEY = "dish_json"


def allergen_key(allergen: Allergen) -> str:
    """Metadata key holding whether a dish contains `allergen`."""
    return f"{ALLERGEN_KEY_PREFIX}{allergen.value}"


def diet_key(flag: DietaryFlag) -> str:
    """Metadata key holding whether a dish carries the dietary `flag`."""
    return f"{DIET_KEY_PREFIX}{flag.value}"


def dish_to_document(dish: Dish) -> str:
    """Build the text that gets embedded for semantic search.

    Allergens are deliberately left out: embeddings do not understand negation, so a
    query like "no peanuts" would be pulled towards dishes that mention peanuts.
    Allergen exclusion is handled by metadata filters instead.
    """
    flags = ", ".join(sorted(dish.dietary_flags)) or "none"
    lines = [
        f"{dish.name} ({dish.course})",
        dish.description,
        f"Ingredients: {', '.join(dish.ingredients)}",
        f"Preparation: {dish.preparation}",
        f"Tags: {', '.join(dish.tags)}",
        f"Dietary: {flags}",
    ]
    return "\n".join(lines)


def dish_to_metadata(dish: Dish) -> dict[str, str | bool]:
    """Build flat metadata for deterministic filtering and for rebuilding the dish.

    Every allergen and dietary flag gets an explicit boolean key, so a filter like
    `allergen_peanuts == False` never depends on a key being absent. The full dish is
    stored as JSON so answers can be grounded in exact menu data.
    """
    metadata: dict[str, str | bool] = {
        "name": dish.name,
        "course": dish.course.value,
        DISH_JSON_KEY: dish.model_dump_json(),
    }
    for allergen in Allergen:
        metadata[allergen_key(allergen)] = allergen in dish.allergens
    for flag in DietaryFlag:
        metadata[diet_key(flag)] = flag in dish.dietary_flags
    return metadata
