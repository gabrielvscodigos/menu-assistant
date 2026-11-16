"""Semantic search over indexed dishes with deterministic allergen and dietary filters.

Filtering happens twice, both in code and never by the LLM:
1. as an exact metadata filter inside the vector store query, and
2. as a final check against the full dish data, so a stale or malformed index entry
   can never leak a dish that breaks the user's restrictions.
"""

import logging

from chromadb.api.models.Collection import Collection
from chromadb.api.types import Where
from pydantic import BaseModel, ConfigDict, Field

from menu_assistant.models import Allergen, Course, DietaryFlag, Dish, NonEmptyStr
from menu_assistant.retrieval.embeddings import Embedder
from menu_assistant.retrieval.metadata import COURSE_KEY, DISH_JSON_KEY, allergen_key, diet_key
from menu_assistant.retrieval.ranking import matched_tags

logger = logging.getLogger(__name__)

MAX_RESULTS = 25
# With tag boosting, re-rank a larger pool so boosted dishes outside the top k can rise.
RERANK_POOL_SIZE = 20


class SearchRequest(BaseModel):
    """What the user is looking for, plus the hard restrictions results must satisfy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: NonEmptyStr
    exclude_allergens: frozenset[Allergen] = frozenset()
    require_flags: frozenset[DietaryFlag] = frozenset()
    course: Course | None = None
    k: int = Field(default=5, ge=1, le=MAX_RESULTS)


class RetrievedDish(BaseModel):
    """A dish returned by search.

    `similarity` is the cosine similarity to the query; `score` adds any tag bonus and
    is what results are ordered by (higher is better).
    """

    model_config = ConfigDict(frozen=True)

    dish: Dish
    similarity: float
    matched_tags: frozenset[str] = frozenset()
    score: float


def build_where(request: SearchRequest) -> Where | None:
    """Translate the request's restrictions into an exact ChromaDB metadata filter."""
    conditions: list[Where] = [
        {allergen_key(allergen): False} for allergen in sorted(request.exclude_allergens)
    ]
    conditions += [{diet_key(flag): True} for flag in sorted(request.require_flags)]
    if request.course is not None:
        conditions.append({COURSE_KEY: request.course.value})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def satisfies(dish: Dish, request: SearchRequest) -> bool:
    """Check the request's restrictions against the dish data itself."""
    return (
        not (dish.allergens & request.exclude_allergens)
        and request.require_flags <= dish.dietary_flags
        and (request.course is None or dish.course == request.course)
    )


class MenuRetriever:
    """Finds the dishes closest to a query among those that pass every restriction."""

    def __init__(self, collection: Collection, embedder: Embedder, tag_boost: float = 0.0) -> None:
        if tag_boost < 0:
            raise ValueError("tag_boost must not be negative")
        self._collection = collection
        self._embedder = embedder
        self._tag_boost = tag_boost

    def search(self, request: SearchRequest) -> list[RetrievedDish]:
        pool_size = max(request.k, RERANK_POOL_SIZE) if self._tag_boost else request.k
        candidates = self._query(request, pool_size)
        ranked = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
        return ranked[: request.k]

    def _query(self, request: SearchRequest, n_results: int) -> list[RetrievedDish]:
        result = self._collection.query(
            query_embeddings=self._embedder.embed_queries([request.query]),
            n_results=n_results,
            where=build_where(request),
            include=["metadatas", "distances"],
        )
        metadatas = result["metadatas"]
        distances = result["distances"]
        if metadatas is None or distances is None:
            raise RuntimeError("vector store returned no metadata or distances")

        candidates: list[RetrievedDish] = []
        for metadata, distance in zip(metadatas[0], distances[0], strict=True):
            dish_json = metadata.get(DISH_JSON_KEY)
            if not isinstance(dish_json, str):
                raise RuntimeError(f"indexed entry is missing '{DISH_JSON_KEY}'; re-run ingestion")
            dish = Dish.model_validate_json(dish_json)
            if not satisfies(dish, request):
                logger.warning(
                    "dropped dish '%s': index metadata disagrees with dish data", dish.id
                )
                continue
            candidates.append(self._score(dish, 1.0 - distance, request.query))
        return candidates

    def _score(self, dish: Dish, similarity: float, query: str) -> RetrievedDish:
        tags = frozenset(matched_tags(query, dish.tags)) if self._tag_boost else frozenset()
        return RetrievedDish(
            dish=dish,
            similarity=similarity,
            matched_tags=tags,
            score=similarity + self._tag_boost * len(tags),
        )
