"""FastAPI application. Run with `uv run uvicorn menu_assistant.api.main:app --reload`."""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from menu_assistant.api.routes import router
from menu_assistant.config import Settings
from menu_assistant.llm.factory import llm_client_from_settings
from menu_assistant.rag.answer import AnswerService
from menu_assistant.retrieval.factory import retriever_from_settings
from menu_assistant.retrieval.vector_store import IndexNotReadyError

logger = logging.getLogger(__name__)

ServiceFactory = Callable[[], AnswerService]


def answer_service_from_settings() -> AnswerService:
    settings = Settings()
    return AnswerService(retriever_from_settings(settings), llm_client_from_settings(settings))


def create_app(service_factory: ServiceFactory = answer_service_from_settings) -> FastAPI:
    """Build the app. Tests pass a factory that returns a service with fakes."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Load the embedding model and open the index once, not per request. If the
        # index is not ready, start anyway so /health can explain what to do.
        app.state.answer_service = None
        app.state.startup_error = None
        try:
            app.state.answer_service = service_factory()
        except IndexNotReadyError as error:
            app.state.startup_error = str(error)
            logger.error("starting without an index: %s", error)
        yield

    app = FastAPI(
        title="menu-assistant",
        summary="Grounded dish suggestions from a restaurant menu.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
