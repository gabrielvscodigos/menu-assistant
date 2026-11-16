"""Request and response bodies of the HTTP API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from menu_assistant.models import Allergen, Course, DietaryFlag
from menu_assistant.rag.answer import Answer
from menu_assistant.retrieval.search import RetrievedDish


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
                }
            ]
        },
    )

    question: str = Field(min_length=1, max_length=500)
    exclude_allergens: list[Allergen] = Field(default_factory=list)
    require_flags: list[DietaryFlag] = Field(default_factory=list)


class DishSource(BaseModel):
    """A dish the answer is based on, with the facts needed to display it."""

    id: str
    name: str
    course: Course
    allergens: list[Allergen]
    dietary_flags: list[DietaryFlag]
    score: float

    @classmethod
    def from_retrieved(cls, item: RetrievedDish) -> "DishSource":
        return cls(
            id=item.dish.id,
            name=item.dish.name,
            course=item.dish.course,
            allergens=sorted(item.dish.allergens),
            dietary_flags=sorted(item.dish.dietary_flags),
            score=round(item.score, 4),
        )


class AppliedRestrictions(BaseModel):
    """Explicit and detected restrictions combined, as enforced by retrieval."""

    exclude_allergens: list[Allergen]
    require_flags: list[DietaryFlag]


class AskResponse(BaseModel):
    """A grounded answer: cited sources, every candidate considered, and the notice."""

    answer: str
    sources: list[DishSource] = Field(description="dishes the answer cites")
    candidates: list[DishSource] = Field(description="all dishes the LLM was given")
    applied_restrictions: AppliedRestrictions
    notice: str | None = Field(description="staff-confirmation notice, if required")

    @classmethod
    def from_answer(cls, answer: Answer) -> "AskResponse":
        return cls(
            answer=answer.text,
            sources=[DishSource.from_retrieved(item) for item in answer.cited_dishes],
            candidates=[DishSource.from_retrieved(item) for item in answer.retrieved],
            applied_restrictions=AppliedRestrictions(
                exclude_allergens=sorted(answer.restrictions.exclude_allergens),
                require_flags=sorted(answer.restrictions.require_flags),
            ),
            notice=answer.notice,
        )


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    detail: str | None = None
