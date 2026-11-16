"""Labeled questions used to measure the quality of generated answers."""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from menu_assistant.models import Allergen, Course, DietaryFlag, DishId, Menu, NonEmptyStr
from menu_assistant.rag.course import detect_course
from menu_assistant.rag.restrictions import Restrictions, detect_restrictions
from menu_assistant.retrieval.search import SearchRequest, satisfies

AnswerCategory = Literal["preference", "restricted", "multilingual", "off_menu"]


class AnswerCase(BaseModel):
    """One guest question and what a good answer to it must do."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: NonEmptyStr
    category: AnswerCategory
    question: NonEmptyStr
    exclude_allergens: frozenset[Allergen] = frozenset()
    require_flags: frozenset[DietaryFlag] = frozenset()
    course: Course | None = None
    relevant: frozenset[DishId] = Field(
        default=frozenset(), description="dishes worth citing; empty if none should be"
    )
    expect_notice: bool
    expect_unavailable: bool = Field(
        default=False, description="the answer must say the menu does not have it"
    )

    @property
    def explicit_restrictions(self) -> Restrictions:
        return Restrictions(
            exclude_allergens=self.exclude_allergens, require_flags=self.require_flags
        )

    def effective_request(self) -> SearchRequest:
        """The filters the system will apply: explicit plus detected, as in production."""
        restrictions = self.explicit_restrictions.merge(detect_restrictions(self.question))
        return SearchRequest(
            query=self.question,
            exclude_allergens=restrictions.exclude_allergens,
            require_flags=restrictions.require_flags,
            course=self.course or detect_course(self.question),
        )


class AnswerDataset(BaseModel):
    """A collection of answer evaluation cases with unique ids."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str = ""
    cases: list[AnswerCase] = Field(min_length=1)

    @model_validator(mode="after")
    def check_case_ids_are_unique(self) -> Self:
        ids = [case.id for case in self.cases]
        duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate case ids: {', '.join(duplicates)}")
        return self


def load_answer_dataset(path: Path) -> AnswerDataset:
    """Read and validate an answer evaluation dataset from a JSON file."""
    return AnswerDataset.model_validate_json(path.read_text(encoding="utf-8"))


def find_answer_labeling_errors(dataset: AnswerDataset, menu: Menu) -> list[str]:
    """Relevant dishes must exist and pass the filters the system will apply."""
    dishes = {dish.id: dish for dish in menu.dishes}
    errors: list[str] = []
    for case in dataset.cases:
        request = case.effective_request()
        for dish_id in sorted(case.relevant):
            dish = dishes.get(dish_id)
            if dish is None:
                errors.append(f"{case.id}: relevant dish '{dish_id}' is not on the menu")
            elif not satisfies(dish, request):
                errors.append(f"{case.id}: relevant dish '{dish_id}' breaks the case filters")
    return errors
