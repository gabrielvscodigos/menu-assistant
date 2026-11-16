# menu-assistant

A RAG-based assistant that helps people choose what to eat from a restaurant menu.
Users ask things like "I like spicy ramen, what else here would I enjoy?" and get
grounded suggestions based on each dish's ingredients, preparation, dietary
restrictions, and allergens.

This is a portfolio project. Prioritize clean architecture, tests, evaluation, and
good documentation over feature count.

## Stack
- Python 3.12, managed with `uv`
- API: FastAPI
- Vector store: ChromaDB (local, persistent)
- Embeddings: sentence-transformers (multilingual model)
- LLM: accessed only through the `LLMClient` interface in `src/menu_assistant/llm/`
  (default provider: Anthropic API; local alternative via Ollama)
- Tests: pytest | Lint/format: ruff | Types: mypy
- Config: pydantic-settings + `.env` (never commit `.env`)

## Commands
- Install: `uv sync`
- Run API: `uv run uvicorn menu_assistant.api.main:app --reload`
- Ingest menu: `uv run python -m menu_assistant.ingest data/menu.json`
- Test: `uv run pytest`
- Lint/format: `uv run ruff check . && uv run ruff format .`
- Type check: `uv run mypy src`
- Evaluate: `uv run python -m menu_assistant.eval`

## Project structure
```
src/menu_assistant/
  api/        FastAPI app and routes
  ingest/     menu loading, validation, chunking, indexing
  retrieval/  embeddings, vector store, filters, ranking
  llm/        LLMClient interface and provider implementations
  rag/        prompt building and answer generation
  eval/       evaluation dataset and metrics
data/         sample (fictional) menu data
tests/        mirrors src/ structure
docs/         architecture notes and decisions
```

## Domain rules (important)
- Each dish is structured data: name, description, ingredients, preparation,
  tags, dietary flags (vegan, vegetarian, gluten-free, halal, ...), and allergens.
- Allergen and dietary filtering MUST be deterministic (metadata filters in code),
  never delegated to the LLM alone.
- The LLM must answer only from retrieved menu data. If the information is not
  in the menu, say so. Never invent ingredients, allergens, or dishes.
- Every answer involving allergens or restrictions must include a short notice
  to confirm with the restaurant staff.
- Always cite which dishes the answer is based on.

## Code conventions
- Everything in English: code, comments, docstrings, docs, commit messages.
- Type hints everywhere; Pydantic models for all data crossing a boundary.
- Keep functions small and single-purpose. No premature abstraction.
- Provider-specific code stays inside `llm/`; the rest of the app depends only on interfaces.
- Write tests with the code. Mock the LLM in unit tests; no network calls in tests.
- Ask before adding a dependency.

## Workflow
- Follow the global rules: small steps, explain each change, propose the commit
  message (Conventional Commits, English), and wait for my approval.
- Keep `README.md` and `docs/` updated as features land.
- When a design choice has trade-offs, write a short note in `docs/decisions.md`.