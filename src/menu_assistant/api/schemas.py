"""Request and response bodies of the HTTP API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from menu_assistant.models import Allergen, Course, DietaryFlag, DishId
from menu_assistant.rag.answer import Answer
from menu_assistant.rag.language import Language
from menu_assistant.retrieval.ingredients import IngredientTerm
from menu_assistant.retrieval.search import RetrievedDish

MAX_HISTORY_TURNS = 20


class ChatTurn(BaseModel):
    """One earlier turn: a question the guest asked, or the answer they got."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AskRequest(BaseModel):
    """A guest question plus restrictions selected explicitly (e.g. in a UI)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "question": "I like spicy ramen, what else here would I enjoy?",
                    "exclude_allergens": ["peanuts"],
                    "require_flags": [],
                    "exclude_ingredients": ["cilantro"],
                    "course": None,
                }
            ]
        },
    )

    question: str = Field(min_length=1, max_length=500)
    exclude_allergens: list[Allergen] = Field(default_factory=list)
    require_flags: list[DietaryFlag] = Field(default_factory=list)
    exclude_ingredients: list[IngredientTerm] = Field(
        default_factory=list,
        max_length=10,
        description="ingredients to avoid, e.g. onion, cilantro (common pt/es words are mapped)",
    )
    course: Course | None = Field(
        default=None, description="only suggest this course; detected from the question if omitted"
    )
    language: Language | None = Field(
        default=None,
        description="reply language chosen by the guest (en, pt, es); detected if omitted",
    )
    exclude_dishes: list[DishId] = Field(
        default_factory=list,
        max_length=100,
        description="dish ids not to suggest, e.g. ones already shown when asking for others",
    )
    history: list[ChatTurn] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_TURNS,
        description=(
            "earlier turns, oldest first, for follow-up questions; restrictions stated in "
            "earlier questions keep applying"
        ),
    )


class DishPrice(BaseModel):
    """A price as an exact decimal string ("14.50") and an ISO 4217 currency code."""

    amount: str
    currency: str


class DishSource(BaseModel):
    """A dish the answer is based on, with the facts needed to display it."""

    id: str
    name: str
    course: Course
    description: str
    ingredients: list[str]
    price: DishPrice
    allergens: list[Allergen]
    dietary_flags: list[DietaryFlag]
    score: float

    @classmethod
    def from_retrieved(cls, item: RetrievedDish) -> "DishSource":
        return cls(
            id=item.dish.id,
            name=item.dish.name,
            course=item.dish.course,
            description=item.dish.description,
            ingredients=list(item.dish.ingredients),
            price=DishPrice(
                amount=f"{item.dish.price.amount:.2f}", currency=item.dish.price.currency
            ),
            allergens=sorted(item.dish.allergens),
            dietary_flags=sorted(item.dish.dietary_flags),
            score=round(item.score, 4),
        )


class AppliedRestrictions(BaseModel):
    """Explicit and detected restrictions combined, as enforced by retrieval."""

    exclude_allergens: list[Allergen]
    require_flags: list[DietaryFlag]
    exclude_ingredients: list[str]
    course: Course | None = None


class AskResponse(BaseModel):
    """A grounded answer: cited sources, every candidate considered, and the notice."""

    answer: str
    sources: list[DishSource] = Field(description="dishes the answer cites")
    candidates: list[DishSource] = Field(description="all dishes the LLM was given")
    applied_restrictions: AppliedRestrictions
    language: Language = Field(
        description="language of the notice and reply: the chosen one, else detected (en, pt, es)"
    )
    notice: str | None = Field(
        description="staff-confirmation notice, if required, in the question's language"
    )

    @classmethod
    def from_answer(cls, answer: Answer) -> "AskResponse":
        return cls(
            answer=answer.text,
            sources=[DishSource.from_retrieved(item) for item in answer.cited_dishes],
            candidates=[DishSource.from_retrieved(item) for item in answer.retrieved],
            applied_restrictions=AppliedRestrictions(
                exclude_allergens=sorted(answer.restrictions.exclude_allergens),
                require_flags=sorted(answer.restrictions.require_flags),
                exclude_ingredients=sorted(answer.restrictions.exclude_ingredients),
                course=answer.course,
            ),
            language=answer.language,
            notice=answer.notice,
        )


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    detail: str | None = None
