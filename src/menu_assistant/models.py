"""Domain models for menu data shared across ingestion, retrieval, and answering."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1)]
DishId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]


class Allergen(StrEnum):
    """The 14 major allergens defined by EU Regulation 1169/2011."""

    CELERY = "celery"
    CRUSTACEANS = "crustaceans"
    EGGS = "eggs"
    FISH = "fish"
    GLUTEN = "gluten"
    LUPIN = "lupin"
    MILK = "milk"
    MOLLUSCS = "molluscs"
    MUSTARD = "mustard"
    PEANUTS = "peanuts"
    SESAME = "sesame"
    SOY = "soy"
    SULPHITES = "sulphites"
    TREE_NUTS = "tree_nuts"


class DietaryFlag(StrEnum):
    """Dietary suitability declared by the restaurant for a dish."""

    VEGAN = "vegan"
    VEGETARIAN = "vegetarian"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"
    HALAL = "halal"


class Course(StrEnum):
    """Where a dish sits in a meal."""

    STARTER = "starter"
    MAIN = "main"
    SIDE = "side"
    DESSERT = "dessert"


# Allergens a dish must not list when it carries the given dietary flag.
FORBIDDEN_ALLERGENS: dict[DietaryFlag, frozenset[Allergen]] = {
    DietaryFlag.VEGAN: frozenset(
        {Allergen.MILK, Allergen.EGGS, Allergen.FISH, Allergen.CRUSTACEANS, Allergen.MOLLUSCS}
    ),
    DietaryFlag.VEGETARIAN: frozenset({Allergen.FISH, Allergen.CRUSTACEANS, Allergen.MOLLUSCS}),
    DietaryFlag.GLUTEN_FREE: frozenset({Allergen.GLUTEN}),
    DietaryFlag.DAIRY_FREE: frozenset({Allergen.MILK}),
}

# Flags that must also be present when the given flag is declared.
IMPLIED_FLAGS: dict[DietaryFlag, frozenset[DietaryFlag]] = {
    DietaryFlag.VEGAN: frozenset({DietaryFlag.VEGETARIAN, DietaryFlag.DAIRY_FREE}),
}


class Dish(BaseModel):
    """A single menu item with the facts the assistant is allowed to rely on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: DishId
    name: NonEmptyStr
    course: Course
    description: NonEmptyStr
    ingredients: list[NonEmptyStr] = Field(min_length=1)
    preparation: NonEmptyStr
    tags: list[Tag] = Field(default_factory=list)
    dietary_flags: frozenset[DietaryFlag] = frozenset()
    allergens: frozenset[Allergen] = frozenset()

    @model_validator(mode="after")
    def check_flags_are_consistent(self) -> Self:
        """Reject dishes whose dietary flags contradict their allergens or each other."""
        for flag in self.dietary_flags:
            conflicting = self.allergens & FORBIDDEN_ALLERGENS.get(flag, frozenset())
            if conflicting:
                names = ", ".join(sorted(conflicting))
                raise ValueError(f"dish '{self.id}' is flagged {flag} but lists allergens: {names}")

            missing = IMPLIED_FLAGS.get(flag, frozenset()) - self.dietary_flags
            if missing:
                names = ", ".join(sorted(missing))
                raise ValueError(
                    f"dish '{self.id}' is flagged {flag} but is missing flags: {names}"
                )
        return self


class Menu(BaseModel):
    """A restaurant menu: the full set of dishes the assistant can recommend."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    restaurant: NonEmptyStr
    dishes: list[Dish] = Field(min_length=1)

    @model_validator(mode="after")
    def check_dish_ids_are_unique(self) -> Self:
        """Reject menus with duplicate dish ids, since ids are used for indexing and citing."""
        seen: set[str] = set()
        duplicates: set[str] = set()
        for dish in self.dishes:
            if dish.id in seen:
                duplicates.add(dish.id)
            seen.add(dish.id)
        if duplicates:
            raise ValueError(f"duplicate dish ids: {', '.join(sorted(duplicates))}")
        return self
