# API image: FastAPI + embedding model on CPU. The LLM runs in a separate Ollama
# container (see compose.yaml). Build: docker build -t menu-assistant .

# --- build stage: resolve and install dependencies from the lockfile ---------------
FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so code changes do not reinstall PyTorch.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# --- runtime stage: only the virtual environment and the menu data -----------------
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=build /app/.venv /app/.venv
COPY data ./data

# Mount points for named volumes: the Hugging Face model cache and the Chroma index.
RUN mkdir -p /app/.cache/huggingface /app/.chroma && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    MENU_ASSISTANT_CHROMA_PATH=/app/.chroma

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10m --retries=3 \
    CMD ["python", "-c", "import urllib.request, sys; sys.exit(0 if b'\"ok\"' in urllib.request.urlopen('http://127.0.0.1:8000/health').read() else 1)"]

# Ingestion is idempotent and fast for one menu, so (re)index on every start. Then
# serve the API on all interfaces so the port can be published.
CMD ["sh", "-c", "python -m menu_assistant.ingest data/menu.json && exec uvicorn menu_assistant.api.main:app --host 0.0.0.0 --port 8000"]
