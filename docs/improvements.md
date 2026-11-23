# Improvements

A log of improvements made after the first complete version (retrieval, grounded
answers, API, evaluation, Docker). Each item records what the project did before, why
that was a problem, what changed, and how it works afterwards. Trade-offs that deserve a
longer note are recorded in [decisions.md](decisions.md).

| #   | Improvement                                         | Status  |
| --- | --------------------------------------------------- | ------- |
| 1   | [Short CLI commands](#1--short-cli-commands)         | done    |
| 2   | [LLM readiness check](#2--llm-readiness-check)       | done    |
| 3   | [Fixed texts in the question's language](#3--fixed-texts-in-the-questions-language) | done    |
| 4   | [Ingredient dislikes](#4--ingredient-dislikes)       | done    |
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

**After:**

- `rag/language.py` detects the language by counting words distinctive for each language
  and letters only one of them uses (`ã`, `ç`, `ñ`, `¿`). Unclear questions fall back to
  English.
- `SAFETY_NOTICES` and `NO_MATCH_TEXTS` in `rag/answer.py` hold each text in the three
  languages; the answer service picks the one for the detected language.
- `Answer.language` and the API response's new `language` field (`en`, `pt`, `es`) show
  which language was detected, so a UI can label its own text to match.

```text
$ uv run menu-ask "Tenho alergia a amendoim, tem algum macarrão apimentado?"
...
Note: As informações sobre alérgenos e restrições alimentares vêm do cardápio e podem
estar incompletas. Confirme com a equipe do restaurante antes de pedir.
```

Checked against all 72 questions in the two evaluation datasets: every full-sentence
question is detected correctly. Three short keyword queries without function words
("fideos picantes", "cordeiro grelhado", "comida mexicana apimentada") fall back to
English, which only affects the notice, since the LLM still answers in the guest's
language. Tests cover each language, the fallback, accents and case, the notice and the
"no match" reply per language, the API field, and that every language has every text.
Trade-offs: [decision 021](decisions.md#021--fixed-texts-follow-the-questions-language-detected-by-word-lists).

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

**After:**

- **Matching** (`retrieval/ingredients.py`): a term excludes a dish when it appears as
  whole words, singular or plural, in any ingredient: `onion` matches "white onion" and
  "sumac onions", `chili` matches "ancho chilies", `pork` matches "guanciale (cured pork
  cheek)", but `pea` does not match "chickpeas".
- **Filtering** (`MenuRetriever`): ingredients are free text, so they cannot be a
  ChromaDB metadata filter. Dishes are checked against their ingredient list after the
  vector search, and the whole menu is fetched when exclusions are present, so `k`
  results are still returned when most of the nearest dishes are excluded.
- **Detection** (`rag/restrictions.py`): a fixed English/Portuguese/Spanish word list
  maps common dislikes to English terms ("cebola" → `onion`, "coentro" → `cilantro` +
  `coriander`, "cogumelo" → `mushroom` + `shiitake`). It reuses the allergen cue rules
  and adds dislike cues ("não gosto de", "odeio", "hate", "hold the"). "I love onions"
  excludes nothing.
- **Explicit input:** `exclude_ingredients` in `POST /ask` and `--without` in the CLI.
  Known Portuguese/Spanish words go through the same list (`--without cebola` → `onion`).
- **Transparency and safety:** the terms appear in `applied_restrictions` and in the
  prompt ("without garlic, onion"), and, like allergens, they trigger the staff notice.

```bash
uv run menu-ask "tacos sem coentro"
uv run menu-ask "a hearty curry" --without onion --without garlic
```

Five labeled retrieval cases were added (`filt-curry-no-onion`, `filt-tacos-sem-coentro`,
...). They score recall@5 = 1.0 and MRR = 1.0 with 0 violations; the full set of 49 cases
went from 0.989 / 0.966 to 0.990 / 0.969. Tests cover matching (plurals, parentheses,
accents, whole words), filtering (including a test that fails if only the top `k` are
fetched), detection in the three languages, the API and CLI inputs, and the prompt.
Trade-offs: [decision 022](decisions.md#022--disliked-ingredients-are-filtered-in-code-after-the-vector-search).

## 5 — Follow-up questions

**Current behavior:** every question is answered on its own. A follow-up such as "and
without gluten?" loses what was asked before.

**Problem:** choosing food is naturally a short conversation. Restrictions stated earlier
("I'm allergic to peanuts") should keep applying to every later turn.

**Change:** `/ask` accepts the previous turns of the conversation (the server stays
stateless). Restrictions are collected from every user turn, so once stated they keep
applying, and the history is passed to the LLM through the existing `ChatMessage` list.

**After:** to be filled in when implemented.
