# Design decisions

Short notes on choices with trade-offs. Newest entries at the bottom.

## 001 — uv for environment and dependency management

**Decision:** use uv for Python installation, virtual environments, dependency
resolution, and the lockfile (`uv.lock`, committed).

**Why:** one fast tool replaces pyenv + venv + pip-tools/Poetry, and the lockfile gives
reproducible installs locally and in CI.

**Trade-off:** contributors need uv installed; plain `pip install -e .` still works
because the project uses standard `pyproject.toml` metadata.

## 002 — `src/` layout

**Decision:** application code lives in `src/menu_assistant/`, tests in `tests/`.

**Why:** tests run against the installed package, not whatever happens to be in the
working directory, which catches packaging mistakes early and avoids accidental imports.

**Trade-off:** slightly more nesting than a flat layout.

## 003 — Strict mypy

**Decision:** run mypy with `strict = true` on both `src` and `tests`.

**Why:** data crosses several boundaries (menu files, vector store, LLM, HTTP), and strict
typing together with Pydantic models catches mismatches before runtime. Starting strict
is much cheaper than tightening later.

**Trade-off:** more annotations, and some third-party libraries without type stubs may
need targeted `ignore_missing_imports` overrides.

## 004 — pytest `importlib` import mode

**Decision:** configure pytest with `--import-mode=importlib`; test folders have no
`__init__.py`.

**Why:** it is the mode pytest recommends for new projects. Test modules do not get
added to `sys.path`, so mirrored test file names across folders cannot clash.

**Trade-off:** test modules cannot import each other directly; shared helpers go in
`conftest.py` fixtures.

## 005 — Closed vocabularies and consistency checks for menu data

**Decision:** allergens, dietary flags, and courses are enums (allergens follow the 14 EU
major allergens). Menu validation rejects unknown fields and values, and rejects dishes
whose flags contradict their allergens (e.g. `vegan` + `eggs`, `gluten_free` + `gluten`).
`vegan` also requires `vegetarian` and `dairy_free`.

**Why:** allergen filtering is deterministic and safety-relevant. With free-text values, a
typo like `"glutten"` would silently slip past a filter. Failing loudly at ingestion is far
safer than a wrong recommendation. Requiring implied flags keeps filters simple: asking
for vegetarian dishes is a single flag check.

**Trade-off:** adding a new allergen or flag needs a code change, and menus must use the
exact vocabulary. Free-form descriptors (`spicy`, `japanese`) stay in open `tags`.

## 006 — Domain models at the package root

**Decision:** `Dish` and `Menu` live in `menu_assistant/models.py`, not inside `ingest/`.

**Why:** ingestion, retrieval, prompt building, and the API all use these models. Keeping
them at the root avoids other packages depending on `ingest` internals.

**Trade-off:** one module outside the planned subpackages.

## 007 — One document per dish, allergens only in metadata

**Decision:** each dish is indexed as a single document (name, course, description,
ingredients, preparation, tags, dietary flags). Allergens are *not* part of the embedded
text. Every allergen and dietary flag is stored as an explicit boolean metadata key
(`allergen_peanuts`, `diet_vegan`, ...), and the full dish is stored as JSON.

**Why:**
- Dishes are short, so splitting them would only fragment context. One document per dish
  keeps results and citations one-to-one with the menu.
- Embeddings do not understand negation: with allergens in the text, "no peanuts" would
  pull peanut dishes *closer*. Exclusion belongs in exact metadata filters.
- Explicit `False` values mean a filter never depends on a key being absent.
- Storing the dish JSON lets answers be grounded in exact menu data without re-reading the
  source file.

**Trade-off:** metadata is larger (one key per allergen and flag), and the index must be
rebuilt if the vocabulary changes.

## 008 — Local multilingual embedding model on CPU-only PyTorch

**Status:** model choice superseded by 010; the rest still applies.

**Decision:** embed with `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
behind an `Embedder` protocol, computed by our code (Chroma's built-in embedding function
is disabled). PyTorch is installed from the CPU-only wheel index.

**Why:** the model is small, runs on CPU, needs no API key, and handles questions in
languages other than the menu's (a Portuguese query finds the right English dish). The
protocol lets tests use a fake embedder, and lets the model be swapped after evaluation.
CPU-only wheels avoid several GB of CUDA libraries locally and in CI.

**Trade-off:** first run downloads ~470 MB; ranking quality is modest for a small model
(to be measured in the evaluation milestone). No GPU acceleration.

## 009 — Restrictions are enforced twice, both in code

**Decision:** a `SearchRequest` carries the query plus hard restrictions (allergens to
exclude, required dietary flags, course). `build_where()` turns them into an exact
ChromaDB metadata filter, and every result is then re-checked against the full dish data
(`satisfies()`) before it is returned. Mismatches are dropped and logged.

**Why:** allergen safety must not depend on a single mechanism. The metadata filter keeps
search efficient and returns the best *allowed* dishes rather than filtering a top-k
afterwards; the second check means a stale or corrupted index entry can never surface a
dish that breaks the user's restrictions.

**Trade-off:** if an index entry is wrong, the search returns fewer than `k` results
instead of failing loudly. The warning in the logs is the signal to re-run ingestion.

## 010 — multilingual-e5-base with a small tag boost

**Decision:** default to `intfloat/multilingual-e5-base` (with its `query: ` /
`passage: ` prefixes) and re-rank a pool of 20 filtered candidates with a `+0.05` bonus
per dish tag named in the query. Each index records the embedding setup it was built
with; search refuses a mismatched index, and ingestion rebuilds it.

**Why:** measured on the evaluation set (see `docs/evaluation.md`), this raised
recall@5 from 0.750 to 0.956 and MRR from 0.783 to 0.934 with zero filter violations.
The model fixes cuisine and multilingual matching; the tag boost fixes attribute words
like "spicy" that small embedding models underweight. The index signature check stops
silently wrong results when the model changes, because vectors from different models
are not comparable.

**Trade-off:** a ~1.1 GB model download and slower embedding than MiniLM;
`multilingual-e5-small` with the same boost (0.904 / 0.894) is the lighter fallback. The
boost weight was tuned on a small set without a held-out split, and tag matching only
works for English queries.

## 011 — LLM behind a small protocol, Ollama over plain HTTP

**Decision:** the app talks to LLMs only through `LLMClient.generate(system, messages)`
in `llm/base.py`. Providers live in `llm/` and are chosen in one factory from settings.
The first provider is a local Ollama server, called directly over HTTP with `httpx`
rather than the `ollama` SDK.

**Why:**
- A one-method protocol is easy to fake in tests and easy to implement for another
  provider without touching retrieval or prompting code.
- A local model means no API key or cost while developing.
- Ollama's chat endpoint is a single JSON call; `httpx` (already used by ChromaDB) covers
  it, and an injectable transport makes tests network-free. Failures become an `LLMError`
  with a fix-it message (start Ollama, `ollama pull <model>`, raise the timeout).

**Trade-off:** we maintain the small request/response mapping ourselves, and the default
`llama3.2` (3B) is fast but weaker at following grounding instructions than larger models.

## 012 — Grounded answering: code decides, the LLM only writes

**Decision:** in `rag/`, everything safety-relevant happens in code around the LLM call:
- Restrictions come from explicit options plus deterministic pattern detection in the
  question (EN/PT/ES); the LLM never decides what to filter.
- If no dish passes the filters, a fixed reply is returned and the LLM is not called.
- The prompt contains only retrieved dishes, with every fact the model may use, and
  asks for `[dish-id]` citations.
- After generation, citations are verified: ids of dishes that were not retrieved are
  removed, and dish names written in brackets are mapped to ids.
- The "confirm with staff" notice is attached by code whenever restrictions were applied
  or the question mentions allergens or diets.

**Why:** the domain rules say allergen filtering must be deterministic, answers must cite
dishes, and allergen answers must carry a notice. Small local models do not follow
instructions reliably, so each rule is enforced where it can be tested.

**Trade-off:** pattern detection can miss unusual phrasings (explicit options are the
reliable path) and is deliberately conservative, so it may exclude a dish the user
mentioned casually. The LLM can still add unsupported side remarks inside its text;
measuring that needs an answer-quality evaluation (planned).

## 013 — API: load once at startup, degrade instead of crashing

**Decision:** `create_app()` builds the `AnswerService` once in the FastAPI lifespan and
keeps it on `app.state`; routes get it through a dependency. If the index is missing or
was built with another model, the app still starts: `/health` reports `degraded` with the
fix, and `/ask` returns `503`. LLM failures also map to `503`. `/ask` is a plain `def`
handler so FastAPI runs it in a worker thread.

**Why:** loading the embedding model per request would take seconds; a missing index is
an operator mistake that deserves a clear message, not a crash loop. Embedding and LLM
calls are blocking, so running them on the event loop would stall every other request.
`create_app()` takes a service factory, so tests run the real app with fakes.

**Trade-off:** fixing the index requires restarting the API after re-ingesting. Requests
are handled by FastAPI's thread pool, which is fine for a demo but not for heavy traffic.

## 014 — Ollama as the only LLM provider

**Decision:** ship only the local Ollama provider. The original plan named a hosted API
as the default; it is dropped for now.

**Why:** the project must run end to end with no API key, account, or cost, for the
author and for anyone cloning it. The `LLMClient` protocol keeps the door open: a hosted
provider is one new module in `llm/` plus a factory branch (see
[architecture.md](architecture.md#extending)).

**Trade-off:** answer quality is bounded by models that run on a laptop (`llama3.2` 3B
by default), which follow grounding instructions less reliably than large hosted models.
The code-side checks in decision 012 exist largely to compensate.

## 015 — Course requests are detected in code and filter retrieval

**Decision:** `rag/course.py` detects an explicitly named course (EN/PT/ES: "dessert",
"sobremesa", "postre", "main course", "entrada", ...) and passes it to retrieval as an
exact filter. An explicit `--course` / API `course` wins. Vague words ("something
sweet"), negations ("no dessert"), and questions naming several courses set no filter.
The course is not part of `Restrictions`, so it never triggers the safety notice.

**Why:** the 3B model ignored the course asked for ("vegan dessert" also got a starter).
Filtering before generation means the model only ever sees dishes of that course, the
same "code decides, the LLM only writes" approach as allergens.

**Trade-off:** an explicit course with nothing matching gives the "no match" reply rather
than a near miss from another course. Detection is a word list: "entrée" is left out
because it means a main in the US and a starter elsewhere, and bare "main" is ignored
because of phrases like "main ingredient".

## 016 — Answer quality is measured with deterministic checks, not an LLM judge

**Decision:** `python -m menu_assistant.eval.answers` runs labeled questions through the
real `AnswerService` and scores each reply with rules in code: invented citation ids
(in the raw output), menu dishes named without being retrieved, at least one relevant
citation, at most three recommendations, a correct staff notice, and "not on the menu"
acknowledgement for off-menu questions. Only a notice failure fails the command.

**Why:** the rules mirror the product's promises exactly, cost nothing, and give the same
score for the same reply. The only available model is a local 3B model, which is not a
trustworthy judge. Scoring the raw output shows how much the citation verification is
actually doing.

**Trade-off:** rules cannot judge helpfulness, tone, or the reply's language, and can miss
invented details inside a sentence. The "unavailable" check is a phrase list. Scores
depend on a live model, so the evaluation is not part of CI and results vary slightly
between runs.

## 017 — Docker Compose for a one-command demo

**Decision:** a multi-stage `Dockerfile` builds the API from `uv.lock` (no dev
dependencies, CPU-only PyTorch, non-root user). `compose.yaml` runs it next to the
official Ollama image, with a one-shot service that pulls the model first. The API
container re-runs ingestion on every start; models and the index live in named volumes.

**Why:** a reviewer can try the project without installing Python, uv, or Ollama.
Ingesting one menu takes seconds and is idempotent, so doing it at start-up removes a
manual step and can never leave a stale index. Models are downloaded at run time instead
of baked into the image, which keeps the image small and the build fast.

**Trade-off:** the first start is slow (about 3 GB of downloads), and Ollama runs on CPU
unless GPU access is configured for the container. Re-ingesting at every start would be
wasteful for large menus; then ingestion should become a separate job.

## 018 — Every recommended list item must point at a retrieved dish

**Decision:** after citation verification, `enforce_list_citations` checks each top-level
list item of the reply. Items citing or naming a retrieved dish are kept (a missing
citation is added); any other item is removed, logged, recorded in
`Answer.removed_items`, and numbered lists are renumbered. The answer evaluation counts
these removals (`items`).

**Why:** a Docker smoke test showed `llama3.2` listing "Coconut Ice Cream" and "Fresh
Fruit Salad", which are not on the menu, without brackets, so citation checks never saw
them. Recommendations are almost always written as lists, so a list item is the natural
unit to enforce "never invent dishes" in code. In the evaluation it also removed a real
dish the guest's gluten restriction had excluded.

**Trade-off:** a top-level bullet that is not a dish (e.g. "- All options are vegan") is
removed too, and the reply's text may still say "three options" after one is dropped.
Invented dishes in running prose are not caught; the prompt rule and the `noleak` check
are the only defenses there.

## 019 — Brazilian Portuguese through tag aliases, not translated tags

**Decision:** keep menu tags in English and map ~60 common Portuguese words to them in
`retrieval/ranking.py` (`TAG_ALIASES`). Tag matching strips accents. CLIs force UTF-8
output.

**Why:** the pt-BR baseline showed that the embedding model handles what a dish *is* in
Portuguese, but Portuguese attribute words ("apimentado", "crocante", "frango") got no tag
boost. Aliases raised multilingual recall@5 from 0.765 to 1.000 and MRR from 0.623 to
0.941 without touching preference or filtered scores. Aliases are code, reviewed and
tested once, and menus keep a single tag vocabulary. Translating tags per menu or adding
a translation model would add work for every menu or a heavy dependency.

**Trade-off:** the alias list is hand-written and covers common culinary words only; a
tag without an alias falls back to plain semantic search. Spanish is only covered where
words coincide (`picante`). Like the boost weight, the aliases were checked on an eval
set written by the same author.

## 020 — LLM readiness is checked live, not at startup

**Decision:** `LLMClient` has a `check()` method (for Ollama: `GET /api/tags` and look for
the configured model, accepting `llama3.2` for `llama3.2:latest`). `/health` calls it on
every request with a 5-second timeout and reports `degraded` with the fix. The API still
starts when the LLM is down; the CLI calls `check()` before loading the embedding model.

**Why:** "Ollama not running" and "model not pulled" are the most common setup mistakes,
and before this `/health` said `ok` while every `/ask` failed. Checking at startup only
would force an API restart after starting Ollama; checking live picks it up immediately.
Listing models is cheap and does not load the model into memory, unlike a test prompt.

**Trade-off:** `/health` now depends on Ollama's latency (up to 5 s when it hangs), and
a probe hitting it often adds a small load on Ollama. The check proves the model is
pulled, not that it can generate (e.g. out of memory still shows up only on `/ask`).

## 021 — Fixed texts follow the question's language, detected by word lists

**Decision:** the staff-confirmation notice and the "no match" reply exist in English,
Portuguese, and Spanish. `rag/language.py` picks the language by counting common words
distinctive for each one (`voce`, `quero`, `uma` / `quiero`, `una`, `los` / `the`,
`want`, ...) plus letters only one language uses (`ã`, `ç` / `ñ`, `¿`), falling back to
English. The detected language is returned in `Answer.language` and the API response.

**Why:** the notice is a safety rule, so it must be readable by the guest, and it is
written in code precisely so it never depends on the LLM. Detection follows the same
pattern as restriction and course detection: small, deterministic, and testable. A
language-detection library would be a new dependency and is unreliable on the very short
texts guests type.

**Trade-off:** keyword-only queries with no function words ("fideos picantes",
"cordeiro grelhado") fall back to English; the LLM's reply is still in the guest's
language, so only the notice is affected. Adding a language means a word list plus a
translation of each fixed text (a test checks every language has every text). CLI labels
(`Sources`, `Note`) stay in English.

## 022 — Disliked ingredients are filtered in code, after the vector search

**Decision:** guests can exclude ingredients explicitly (`exclude_ingredients`,
`--without`) or in the question ("no cilantro", "sem cebola", "no me gustan los
tomates"). Detection uses a fixed English/Portuguese/Spanish word list mapped to English
terms, with the same cue rules as allergens. A term excludes a dish when it appears as
whole words, singular or plural, in any of its ingredients. The filter runs in
`MenuRetriever` against the dish data; when it is active the whole menu is fetched, and
the restriction triggers the staff notice like allergens do.

**Why:** the project rule is that restrictions are enforced in code, never by the LLM
alone, and small models are unreliable at skipping a dish they were handed. Ingredients
are free text, so unlike allergens they cannot become boolean metadata keys; matching
words in code keeps the filter exact and testable. Fetching the whole menu guarantees `k`
results even when most of the nearest dishes are excluded (a test proves the top-`k` pool
alone would not be enough).

**Trade-off:** matching is deliberately broad within whole words: "rice" also excludes a
dish with rice vinegar. Ingredients hidden inside a component the menu does not break down
(an onion in a sauce listed as "tomato sauce") cannot be caught, which is one more reason
for the staff notice. Explicit terms go through the same word list ("cebola" → `onion`);
other words are matched as given, so they must be in English like the menu. Fetching the whole menu is fine for restaurant menus
(dozens to a few hundred dishes), not for large catalogs.

## 023 — Follow-up questions: stateless history, restrictions never lifted

**Decision:** `/ask` accepts the earlier turns in `history` and the CLI has a `--chat`
mode; the server stores nothing. For each question, restrictions detected in every
earlier user turn are merged in, the retrieval query adds the last two user turns, and
the last six turns go to the LLM before the message with the retrieved dishes. A prompt
rule says earlier turns are context only. The course comes from the current question.

**Why:** a stateless API keeps the server simple (no sessions, no storage, no expiry) and
lets any client own the conversation. Keeping restrictions across turns is the safety
point: a guest who said "I'm allergic to peanuts" should not have to repeat it.
Restrictions are read only from user turns, so a model reply can never add or remove
one. Adding earlier user turns to the query makes short follow-ups ("and without
gluten?") search for the right thing without asking the LLM to rewrite the question,
which would put an LLM call in front of retrieval. Citation checks already drop any dish
that was not retrieved for the current question, including dishes from earlier replies.

**Trade-off:** a restriction cannot be lifted by saying so ("actually, I can eat
peanuts"); the guest starts a new conversation. The course is not carried over, because
"no dessert this time" would otherwise keep the dessert filter; a follow-up that relies on
an earlier course is only steered by the query text. The client can edit the history it
sends, so restrictions are only as trustworthy as the client, as with explicit
restrictions. "Tell me more about the second one" works only if that dish is retrieved
again for the combined query.

## 024 — Front end: React, Vite, TypeScript, Tailwind, Biome

**Decision:** the chat front end lives in `frontend/` as a React 19 single-page app built
with Vite, written in strict TypeScript, styled with Tailwind CSS, and animated with SVG
and Motion for the mascot. Biome lints and formats, Vitest with Testing Library tests,
and pnpm manages packages. In development, Vite proxies `/api/*` to the FastAPI server.

**Why:** the backend already does all the work behind one stateless endpoint, so the front
end only needs to render a conversation; a single-page app served as static files is
enough, and a framework with its own server (Next.js) would add a second backend. React
has the largest ecosystem and is what most readers of a portfolio know. Tailwind keeps
styling consistent without a separate CSS architecture. Drawing the mascot as SVG and
animating its moods in code needs no design tool and keeps every state testable. Biome is
one fast tool for lint and format, the same role ruff plays on the Python side. The dev
proxy gives the browser one origin, so the API needs no CORS settings.

**Trade-off:** two toolchains (uv and pnpm) in one repository, and a second CI job. The
current jsdom major (30+) needs Node 22.22 or newer, so jsdom is pinned to 29 to support
the Node 22.13 used locally; moving to a newer Node lifts that pin. A static single-page
app has no server-side rendering, which a chat behind an interactive UI does not need.

## 025 — The OpenAPI schema is the contract between API and front end

**Decision:** `python -m menu_assistant.api.openapi` writes the API's OpenAPI schema to
`frontend/openapi.json`, which is committed. The front end generates its TypeScript types
from it with openapi-typescript (`pnpm gen:api`). A Python test fails when the committed
schema differs from the API, and CI fails when the generated types differ from the schema.

**Why:** the front end and back end live in one repository but in two languages. With
hand-written TypeScript types, a renamed or added field would only show up as a runtime
bug in the browser. Generating the types makes the compiler catch it, and the two checks
make it impossible to change one side and forget the other. Committing the schema keeps
type generation independent of a running server.

**Trade-off:** changing the API means running two commands. openapi-typescript still
needs the TypeScript 5 compiler API, which TypeScript 7 (used by the app) no longer
provides, so it runs through `pnpm dlx` with pinned versions instead of being a project
dependency; that downloads it on first use.

## 026 — The mascot is static artwork, not an animated drawing

**Decision:** the waiter mascot is the project's own character artwork (made with an AI
image tool), shown as two PNG images cut from it: the full figure and a head-and-shoulders
avatar. This replaces the animated SVG + Motion mascot planned in decision 024, and Motion
is no longer a dependency.

**Why:** hand-drawn SVG versions of the character did not match the artwork's quality,
and a good-looking static mascot is worth more than an animated one that looks off. The
images are generated by a small PowerShell script from the committed source artwork, so
new or improved artwork can replace them in one step.

**Trade-off:** the mascot no longer reacts to the conversation (thinking, talking,
worried); the "Checking the menu…" message and error bubbles carry that state instead.
Animation can come back later with artwork made for it (for example separate pose images
or a Rive file). The processing script needs Windows PowerShell.

## 027 — Dishes have prices, and the index records its data format

**Decision:** every dish has a `price` (`amount` as an exact decimal with two places,
`currency` as an ISO 4217 code), and a menu must use one currency. The price is part of
the dish facts the LLM sees, the API returns it, and the chat cards show it. The index
signature now includes `INDEX_FORMAT_VERSION`, bumped to 2 by this change.

**Why:** a guest choosing what to eat wants to know the price, and the chat lets them pick
dishes and order. Decimals avoid float rounding (`0.1 + 0.2`); a single currency keeps
totals meaningful. Before this, the index signature only covered the embedding model, so an
index built before prices existed would have failed at query time with a validation error;
with the format version it fails at startup with the usual "re-run ingestion" message.

**Trade-off:** the sample prices are fictional, like the menu. The "price" off-menu
evaluation case became a preference case (the price is now answerable) and was replaced
by a calories question. Existing local indexes must be rebuilt once.

## 028 — Dish translations live on the dish; safety data stays canonical

**Decision:** a dish can carry `translations` per language (`pt` today) with the
guest-facing text (name, description, ingredients, preparation) and a local `price`
(BRL for Portuguese). After retrieval and filtering, the answer service swaps in the
translation for the reply language, so the LLM, the citations, the API, and the cards all
use it. Allergens, dietary flags, tags, and the English ingredient list are never
translated; they stay on the dish and drive every filter.

**Why:** a Brazilian guest should read "Espaguete à Carbonara" for R$ 56,90, not an English
menu in dollars. Keeping translations next to the dish (instead of a second menu file)
means one dish id, one set of allergens, and one place to review: a translated menu can
never drift into different safety data. Ingredient dislikes keep working in every
language because "sem cebola" maps to the canonical `onion`, which is matched against the
English list. Prices are set per language rather than converted, the way a real menu is
priced locally.

**Trade-off:** each translation is written and reviewed by hand, and a dish without one
falls back to English (Spanish has none yet). The embeddings still come from the English
text, which the multilingual model handles well (see the pt-BR retrieval results), but
Portuguese-only words in a translated name are not indexed. The index format version
went to 3, so local indexes need one rebuild. Orders mixing languages show one total per
currency instead of adding R$ and US$ together.
