"""Run the retrieval evaluation and summarize the results."""

from pydantic import BaseModel, ConfigDict

from menu_assistant.eval.dataset import Category, EvalCase, EvalDataset
from menu_assistant.eval.metrics import mean, recall_at_k, reciprocal_rank
from menu_assistant.retrieval.search import MenuRetriever, satisfies


class CaseResult(BaseModel):
    """Outcome of a single evaluation case."""

    model_config = ConfigDict(frozen=True)

    case: EvalCase
    retrieved_ids: list[str]
    recall: float
    reciprocal_rank: float
    violations: int


class Summary(BaseModel):
    """Aggregate scores over a group of cases."""

    model_config = ConfigDict(frozen=True)

    cases: int
    recall: float
    mrr: float
    violations: int


class EvalReport(BaseModel):
    """Per-case results plus overall and per-category summaries."""

    model_config = ConfigDict(frozen=True)

    k: int
    results: list[CaseResult]

    def summary(self, category: Category | None = None) -> Summary:
        selected = [r for r in self.results if category is None or r.case.category == category]
        return Summary(
            cases=len(selected),
            recall=mean([r.recall for r in selected]),
            mrr=mean([r.reciprocal_rank for r in selected]),
            violations=sum(r.violations for r in selected),
        )


def evaluate_case(retriever: MenuRetriever, case: EvalCase, k: int) -> CaseResult:
    request = case.to_request(k)
    retrieved = retriever.search(request)
    retrieved_ids = [r.dish.id for r in retrieved]
    return CaseResult(
        case=case,
        retrieved_ids=retrieved_ids,
        recall=recall_at_k(retrieved_ids, case.relevant, k),
        reciprocal_rank=reciprocal_rank(retrieved_ids, case.relevant),
        violations=sum(not satisfies(r.dish, request) for r in retrieved),
    )


def evaluate(retriever: MenuRetriever, dataset: EvalDataset, k: int) -> EvalReport:
    """Run every case in `dataset` against `retriever`, keeping the top `k` results."""
    return EvalReport(k=k, results=[evaluate_case(retriever, case, k) for case in dataset.cases])
