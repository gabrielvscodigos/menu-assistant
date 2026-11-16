"""Tests for running the evaluation and rendering its report, using a fake embedder."""

import pytest
from chromadb.api.models.Collection import Collection

from menu_assistant.eval.dataset import EvalDataset
from menu_assistant.eval.report import format_report
from menu_assistant.eval.runner import evaluate
from menu_assistant.ingest.documents import dish_to_document
from menu_assistant.ingest.indexer import index_menu
from menu_assistant.models import Menu
from menu_assistant.retrieval.embeddings import Embedder
from menu_assistant.retrieval.search import MenuRetriever


@pytest.fixture
def retriever(sample_menu: Menu, collection: Collection, fake_embedder: Embedder) -> MenuRetriever:
    index_menu(sample_menu, collection, fake_embedder)
    return MenuRetriever(collection, fake_embedder)


@pytest.fixture
def dataset(sample_menu: Menu) -> EvalDataset:
    """Two cases: one whose query is an exact dish document, one that misses."""
    edamame = next(d for d in sample_menu.dishes if d.id == "edamame")
    return EvalDataset.model_validate(
        {
            "cases": [
                {
                    "id": "exact",
                    "category": "preference",
                    "query": dish_to_document(edamame),
                    "relevant": ["edamame"],
                },
                {
                    "id": "filtered-miss",
                    "category": "filtered",
                    "query": dish_to_document(edamame),
                    "exclude_allergens": ["soy"],
                    "relevant": ["chana-masala"],
                    "course": "main",
                },
            ]
        }
    )


def test_exact_match_scores_perfectly(retriever: MenuRetriever, dataset: EvalDataset) -> None:
    report = evaluate(retriever, dataset, k=3)

    exact = report.results[0]
    assert exact.retrieved_ids[0] == "edamame"
    assert exact.recall == 1.0
    assert exact.reciprocal_rank == 1.0


def test_filters_are_applied_and_never_violated(
    retriever: MenuRetriever, dataset: EvalDataset, sample_menu: Menu
) -> None:
    report = evaluate(retriever, dataset, k=25)

    filtered = report.results[1]
    soy_dishes = {d.id for d in sample_menu.dishes if "soy" in d.allergens}
    assert not soy_dishes & set(filtered.retrieved_ids)
    assert report.summary().violations == 0


def test_summary_groups_by_category(retriever: MenuRetriever, dataset: EvalDataset) -> None:
    report = evaluate(retriever, dataset, k=3)

    assert report.summary("preference").cases == 1
    assert report.summary("filtered").cases == 1
    assert report.summary("multilingual").cases == 0
    assert report.summary().cases == 2


def test_report_shows_scores_and_optional_cases(
    retriever: MenuRetriever, dataset: EvalDataset
) -> None:
    report = evaluate(retriever, dataset, k=3)

    short = format_report(report)
    detailed = format_report(report, show_cases=True)

    assert "recall@3" in short
    assert "overall" in short
    assert "exact" not in short
    assert "edamame*" in detailed
    assert "filtered-miss" in detailed
