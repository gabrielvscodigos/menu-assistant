"""Labeled retrieval queries used to measure search quality."""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from menu_assistant.models import Allergen, Course, DietaryFlag, DishId, Menu, NonEmptyStr
from menu_assistant.retrieval.ingredients import IngredientTerm
from menu_assistant.retrieval.search import SearchRequest, satisfies

Category = Literal["preference", "filtered", "multilingual"]


class EvalCase(BaseModel):
    """One query, its hard restrictions, and every dish that counts as a good answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: NonEmptyStr
    category: Category
    query: NonEmptyStr
    exclude_allergens: frozenset[Allergen] = frozenset()
    require_flags: frozenset[DietaryFlag] = frozenset()
    exclude_ingredients: frozenset[IngredientTerm] = frozenset()
    course: Course | None = None
    relevant: frozenset[DishId] = Field(min_length=1)

    def to_request(self, k: int) -> SearchRequest:
        return SearchRequest(
            query=self.query,
            exclude_allergens=self.exclude_allergens,
            require_flags=self.require_flags,
            exclude_ingredients=self.exclude_ingredients,
            course=self.course,
            k=k,
        )


class EvalDataset(BaseModel):
    """A collection of evaluation cases with unique ids."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str = ""
    cases: list[EvalCase] = Field(min_length=1)

    @model_validator(mode="after")
    def check_case_ids_are_unique(self) -> Self:
        ids = [case.id for case in self.cases]
        duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate case ids: {', '.join(duplicates)}")
        return self


def load_dataset(path: Path) -> EvalDataset:
    """Read and validate an evaluation dataset from a JSON file."""
    return EvalDataset.model_validate_json(path.read_text(encoding="utf-8"))


def find_labeling_errors(dataset: EvalDataset, menu: Menu) -> list[str]:
    """Return problems with the labels themselves, checked against the menu.

    A relevant dish must exist on the menu and must pass the case's own restrictions;
    otherwise the case would reward (or be impossible for) a correct retriever.
    """
    dishes = {dish.id: dish for dish in menu.dishes}
    errors: list[str] = []
    for case in dataset.cases:
        request = case.to_request(k=1)
        for dish_id in sorted(case.relevant):
            dish = dishes.get(dish_id)
            if dish is None:
                errors.append(f"{case.id}: relevant dish '{dish_id}' is not on the menu")
            elif not satisfies(dish, request):
                errors.append(f"{case.id}: relevant dish '{dish_id}' breaks the case restrictions")
    return errors
