"""Tests for the evaluation dataset, including the bundled labels."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from menu_assistant.eval.dataset import EvalDataset, find_labeling_errors, load_dataset
from menu_assistant.models import Menu

DATASET_PATH = Path(__file__).parents[2] / "data" / "eval" / "retrieval_queries.json"


def make_case(case_id: str, **overrides: object) -> dict[str, object]:
    return {
        "id": case_id,
        "category": "preference",
        "query": "q",
        "relevant": ["edamame"],
    } | overrides


def test_bundled_dataset_labels_are_consistent_with_the_menu(sample_menu: Menu) -> None:
    dataset = load_dataset(DATASET_PATH)

    assert find_labeling_errors(dataset, sample_menu) == []
    assert len(dataset.cases) >= 30
    assert {case.category for case in dataset.cases} == {"preference", "filtered", "multilingual"}


def test_unknown_dish_is_a_labeling_error(sample_menu: Menu) -> None:
    dataset = EvalDataset.model_validate({"cases": [make_case("c1", relevant=["no-such-dish"])]})

    assert find_labeling_errors(dataset, sample_menu) == [
        "c1: relevant dish 'no-such-dish' is not on the menu"
    ]


def test_relevant_dish_breaking_restrictions_is_a_labeling_error(sample_menu: Menu) -> None:
    case = make_case("c1", relevant=["dan-dan-noodles"], exclude_allergens=["peanuts"])
    dataset = EvalDataset.model_validate({"cases": [case]})

    assert find_labeling_errors(dataset, sample_menu) == [
        "c1: relevant dish 'dan-dan-noodles' breaks the case restrictions"
    ]


def test_duplicate_case_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate case ids: c1"):
        EvalDataset.model_validate({"cases": [make_case("c1"), make_case("c1")]})


def test_case_needs_at_least_one_relevant_dish() -> None:
    with pytest.raises(ValidationError):
        EvalDataset.model_validate({"cases": [make_case("c1", relevant=[])]})
