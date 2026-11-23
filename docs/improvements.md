# Improvements

A log of improvements made after the first complete version (retrieval, grounded
answers, API, evaluation, Docker). Each item records what the project did before, why
that was a problem, what changed, and how it works afterwards. Trade-offs that deserve a
longer note are recorded in [decisions.md](decisions.md).

| #   | Improvement                                         | Status  |
| --- | --------------------------------------------------- | ------- |
| 1   | [Short CLI commands](#1--short-cli-commands)         | done    |
| 2   | [LLM readiness check](#2--llm-readiness-check)       | done    |
| 3   | [Fixed texts in the question's language](#3--fixed-texts-in-the-questions-language) | planned |
| 4   | [Ingredient dislikes](#4--ingredient-dislikes)       | planned |
| 5   | [Follow-up questions](#5--follow-up-questions)       | planned |

## 1 — Short CLI commands

**Current behavior:** every command runs a module by its full path:
`uv run python -m menu_assistant.rag "question"`, and likewise for `ingest` and `eval`.

**Problem:** the commands are long and hard to remember, which is what people type most
often when trying the project.

**Change:** register console scripts in `pyproject.toml` (`[project.scripts]`) that point
at the existing `main()` functions. The `python -m` forms keep working.

**After:** `uv sync` installs four commands into the project environment:

| Command             | Replaces                                     |
| ------------------- | -------------------------------------------- |
| `menu-ask`          | `python -m menu_assistant.rag`               |
| `menu-ingest`       | `python -m menu_assistant.ingest`            |
| `menu-eval`         | `python -m menu_assistant.eval`              |
| `menu-eval-answers` | `python -m menu_assistant.eval.answers`      |

```bash
uv run menu-ask "gosto de cuscuz, tem algo parecido pra mim?"
```

The names share a `menu-` prefix so they cannot clash with other tools on the `PATH`
(a bare `ask` would). Help output (`--help`) shows the short names. A test checks that
each script is registered and points at a callable `main`.

## 2 — LLM readiness check

**Current behavior:** the app only checks the vector index at startup. `/health` reports
`ok` even when Ollama is not running or the configured model is not pulled. The CLI loads
the embedding model and searches the menu first, and only then fails with
`cannot reach Ollama`.

**Problem:** the most common setup mistake (Ollama not started, model not pulled) is
reported late and only when a question is asked. A health check that says `ok` while
every `/ask` would return 503 is misleading.

**Change:** add a readiness check to the `LLMClient` side (for Ollama: list the local
models and confirm the configured one is there). `/health` reports the LLM status, and the
CLI checks it before loading the embedding model.

**After:**

- `LLMClient` gained a `check()` method. `OllamaClient.check()` calls `GET /api/tags`
  (5-second timeout) and confirms the configured model is pulled; `llama3.2` matches
  `llama3.2:latest`.
- `/health` runs the check on every call, so starting Ollama or pulling the model is
  picked up without restarting the API:

  ```json
  {"status": "degraded", "detail": "LLM unavailable: model 'llama3.2' is not available in Ollama; run `ollama pull llama3.2`"}
  ```

- `menu-ask` checks the LLM first and exits in milliseconds with the same message,
  instead of loading the embedding model and searching the menu before failing.
- The API still starts without the LLM, as it already did without an index.

Tests cover the Ollama check (model present under both spellings, missing model,
unreachable server, malformed response), `/health` with an unavailable LLM, and the CLI
failing before it loads the index. Why the check is live rather than at startup:
[decision 020](decisions.md#020--llm-readiness-is-checked-live-not-at-startup).

## 3 — Fixed texts in the question's language

**Current behavior:** the LLM answers in the guest's language, but the fixed texts written
in code (the safety notice about allergens and the "no dish matches" reply) are always in
English.

**Problem:** a Portuguese question gets a Portuguese answer followed by an English safety
notice. That notice is a product rule ("confirm with the restaurant staff"), so it should
be as clear as the answer itself.

**Change:** detect the question's language deterministically (English, Portuguese,
Spanish; English as fallback) and pick the fixed texts from a small translation table.

**After:** to be filled in when implemented.

## 4 — Ingredient dislikes

**Current behavior:** hard restrictions cover the 14 allergens and the dietary flags.
"No cilantro" or "sem cebola" is not a restriction: the dish can still be retrieved and
recommended, and only the LLM may notice the request.

**Problem:** the project rule is that restrictions are enforced in code, never by the LLM
alone. Dislikes are softer than allergies, but a guest who says "no onions" and gets an
onion dish has a worse experience, and the LLM is unreliable at this.

**Change:** add excluded ingredients as a deterministic filter: an explicit
`exclude_ingredients` field in the API and CLI, plus detection of phrases like "without X",
"sem X", "sin X" in the question. Matching runs against each dish's ingredient list.
Open question for implementation: ingredients are written in English, so Portuguese and
Spanish words need a mapping, as the tag aliases do.

**After:** to be filled in when implemented.

## 5 — Follow-up questions

**Current behavior:** every question is answered on its own. A follow-up such as "and
without gluten?" loses what was asked before.

**Problem:** choosing food is naturally a short conversation. Restrictions stated earlier
("I'm allergic to peanuts") should keep applying to every later turn.

**Change:** `/ask` accepts the previous turns of the conversation (the server stays
stateless). Restrictions are collected from every user turn, so once stated they keep
applying, and the history is passed to the LLM through the existing `ChatMessage` list.

**After:** to be filled in when implemented.
