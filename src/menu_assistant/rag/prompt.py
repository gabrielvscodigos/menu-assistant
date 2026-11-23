"""Prompt construction: the LLM only ever sees dishes that passed retrieval and filters."""

from collections.abc import Sequence

from menu_assistant.models import Course, Dish
from menu_assistant.rag.restrictions import Restrictions
from menu_assistant.retrieval.search import RetrievedDish

SYSTEM_PROMPT = """\
You are a friendly server at a restaurant, helping a guest choose what to eat.

Rules:
1. Use ONLY the dishes listed under MENU DISHES. Never mention or suggest any other \
dish, not even common ones like ice cream or fruit salad.
2. Never invent or guess ingredients, allergens, preparation, or prices. If the guest \
asks about something the listed information does not cover, say that the menu does not \
say.
3. Cite every dish you mention right after its name, using its id in square brackets, \
for example: Spicy Miso Ramen [spicy-miso-ramen].
4. Recommend at most 3 dishes, and say briefly why each fits what the guest asked for.
5. If none of the listed dishes fit the request, say so honestly.
6. Hard restrictions were already applied: every listed dish satisfies them, so do not \
reject a listed dish because of them, and never say a listed dish contains something the \
guest must avoid. The Allergens line is complete; do not guess allergens from ingredient \
names. Do not suggest that the guest can ignore the restrictions.
7. Answer in the same language as the guest's question. Keep it short and warm.
8. Earlier turns of the conversation are context only. Suggest dishes only from the \
MENU DISHES in the latest message, even if an earlier reply mentioned others.\
"""


def format_dish(dish: Dish) -> str:
    """Render one dish with every fact the LLM is allowed to use."""
    flags = ", ".join(sorted(dish.dietary_flags)) or "none declared"
    allergens = ", ".join(sorted(dish.allergens)) or "none listed"
    return "\n".join(
        [
            f"[{dish.id}] {dish.name} ({dish.course})",
            f"Description: {dish.description}",
            f"Ingredients: {', '.join(dish.ingredients)}",
            f"Preparation: {dish.preparation}",
            f"Tags: {', '.join(dish.tags) or 'none'}",
            f"Dietary: {flags}",
            f"Allergens: {allergens}",
        ]
    )


def format_restrictions(restrictions: Restrictions) -> str:
    if not restrictions:
        return "none"
    parts = []
    if restrictions.exclude_allergens:
        parts.append(f"excludes {', '.join(sorted(restrictions.exclude_allergens))}")
    if restrictions.require_flags:
        parts.append(f"must be {', '.join(sorted(restrictions.require_flags))}")
    if restrictions.exclude_ingredients:
        parts.append(f"without {', '.join(sorted(restrictions.exclude_ingredients))}")
    return "; ".join(parts)


def build_user_message(
    question: str,
    retrieved: Sequence[RetrievedDish],
    restrictions: Restrictions,
    course: Course | None = None,
) -> str:
    """Combine the guest's question with the retrieved dishes, best match first."""
    dishes = "\n\n".join(format_dish(item.dish) for item in retrieved)
    course_line = f"COURSE REQUESTED: {course} (only this course is listed)\n\n" if course else ""
    return (
        f"MENU DISHES (best matches first):\n\n{dishes}\n\n"
        f"HARD RESTRICTIONS ALREADY APPLIED: {format_restrictions(restrictions)}\n\n"
        f"{course_line}"
        f"GUEST QUESTION: {question}"
    )
