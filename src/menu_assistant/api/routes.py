"""HTTP routes. Handlers stay thin: validation in schemas, logic in `rag`."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from menu_assistant.api.schemas import AskRequest, AskResponse, HealthResponse
from menu_assistant.llm import LLMError
from menu_assistant.rag.answer import AnswerService
from menu_assistant.rag.restrictions import Restrictions, ingredient_terms

router = APIRouter()


def get_answer_service(request: Request) -> AnswerService:
    """The service built at startup; 503 if the app could not build it."""
    service: AnswerService | None = request.app.state.answer_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=request.app.state.startup_error,
        )
    return service


@router.get("/health")
def health(request: Request) -> HealthResponse:
    """Liveness plus readiness: `degraded` means `/ask` would fail, and `detail` says why.

    Checks the index (once, at startup) and the LLM (on every call, with a short
    timeout), so starting Ollama or pulling the model is picked up without a restart.
    """
    service: AnswerService | None = request.app.state.answer_service
    if service is None:
        return HealthResponse(status="degraded", detail=request.app.state.startup_error)
    try:
        service.check_llm()
    except LLMError as error:
        return HealthResponse(status="degraded", detail=f"LLM unavailable: {error}")
    return HealthResponse(status="ok")


@router.post("/ask", responses={503: {"description": "Index not ready or LLM unavailable"}})
def ask(
    body: AskRequest, service: Annotated[AnswerService, Depends(get_answer_service)]
) -> AskResponse:
    """Suggest dishes for a question, grounded in the menu and its restrictions.

    Declared as a plain `def` so FastAPI runs it in a worker thread: embedding and
    LLM calls are blocking and must not stall the event loop.
    """
    explicit = Restrictions(
        exclude_allergens=frozenset(body.exclude_allergens),
        require_flags=frozenset(body.require_flags),
        exclude_ingredients=ingredient_terms(body.exclude_ingredients),
    )
    try:
        answer = service.answer(body.question, explicit, body.course)
    except LLMError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"LLM unavailable: {error}"
        ) from error
    return AskResponse.from_answer(answer)
