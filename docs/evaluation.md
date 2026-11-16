# Evaluation

Two evaluations: **retrieval** (are the right dishes found?) and **answer quality**
(does the generated reply follow the product's rules?).

# Retrieval evaluation

How search quality is measured, and the results so far.

## Method

[`data/eval/retrieval_queries.json`](../data/eval/retrieval_queries.json) holds 34
hand-labeled queries against the sample menu. Each case has a query, optional hard
restrictions (allergens to exclude, required dietary flags, course), and the set of dishes
a reasonable server would suggest.

| Category       | Cases | What it tests                                                   |
| -------------- | ----: | --------------------------------------------------------------- |
| `preference`   |    16 | Taste-based requests ("I like spicy ramen", "creamy and mild")  |
| `filtered`     |    11 | Requests with allergen, diet, or course restrictions            |
| `multilingual` |     7 | Portuguese and Spanish queries against the English menu         |

Labels are validated before every run: a relevant dish must exist on the menu and must
satisfy the case's own restrictions.

**Metrics** (top `k` = 5):

- **recall@5**: share of the relevant dishes found in the top 5. Capped below 1.0 when a
  case has more than 5 relevant dishes (none currently do).
- **MRR**: mean of 1 / rank of the first relevant dish; rewards putting a good dish first.
- **violations**: results that break a hard restriction. Must always be **0**; the
  command exits with status 1 otherwise, so it can gate CI.

Run it (after indexing the menu):

```bash
uv run python -m menu_assistant.eval            # summary
uv run python -m menu_assistant.eval --cases    # plus every query, hits marked with *
```

## Results

| Date       | Configuration                                            | recall@5 | MRR   | violations |
| ---------- | -------------------------------------------------------- | -------: | ----: | ---------: |
| 2026-11-16 | Baseline: `paraphrase-multilingual-MiniLM-L12-v2`, cosine |    0.750 | 0.783 |          0 |
| 2026-11-16 | **Current default:** `multilingual-e5-base` + tag boost 0.05 | **0.956** | **0.934** |      0 |

See [Experiment: embedding model × tag boost](#experiment-embedding-model--tag-boost)
for how the default was chosen.

Baseline by category:

| Category     | recall@5 | MRR   |
| ------------ | -------: | ----: |
| preference   |    0.818 | 0.825 |
| filtered     |    0.718 | 0.788 |
| multilingual |    0.643 | 0.679 |

### Baseline observations

- **Filters are exact.** Zero violations; when the filter leaves few candidates
  (`filt-vegan-main`, `filt-halal-meat`), recall is perfect.
- **Attribute words are weak.** "spicy" barely moves the ranking: `spicy noodles`
  returns carbonara first, and `something spicy` misses spicy-miso-ramen, birria, and the
  green curry. The model matches *dish type* far better than *attributes*.
- **Cuisine words are weak.** `Italian food` ranks chana masala and falafel above pizza;
  `Japanese food` misses edamame.
- **Multilingual is the weakest category.** Portuguese and Spanish queries work for
  concrete nouns (`chocolate`, `coco`) but lose attributes (`picante`, `vegano`).
- **Ambiguous label:** `massa italiana com queijo` retrieves margherita pizza first;
  *massa* can mean pasta or dough in Portuguese. The label was kept as pasta-only.

These point at two improvement paths: a stronger embedding model, and using the dish
`tags` (which already encode `spicy`, `italian`, `japanese`, ...) as an explicit ranking
signal.

## Experiment: embedding model × tag boost

**Date:** 2026-11-16. **Question:** do a stronger model and/or a tag-based ranking bonus
fix the weaknesses above?

- **Models:** the baseline MiniLM (~470 MB), `intfloat/multilingual-e5-small`
  (~470 MB), and `intfloat/multilingual-e5-base` (~1.1 GB). E5 models use their
  documented `query: ` / `passage: ` prefixes.
- **Tag boost:** after the filtered vector search returns a pool of 20 allowed
  candidates, each dish gets `+boost` per tag whose words appear in the query (e.g.
  "spicy noodles" matches the tags `spicy` and `noodles`), and the pool is re-sorted.

Overall recall@5 / MRR (violations were 0 in every run):

| Model         | boost 0       | boost 0.05        | boost 0.10    | boost 0.15    |
| ------------- | ------------- | ----------------- | ------------- | ------------- |
| MiniLM-L12    | 0.750 / 0.783 | 0.823 / 0.851     | 0.885 / 0.890 | 0.891 / 0.904 |
| e5-small      | 0.861 / 0.872 | 0.904 / 0.894     | 0.904 / 0.894 | 0.904 / 0.894 |
| e5-base       | 0.925 / 0.875 | **0.956 / 0.934** | 0.956 / 0.919 | 0.956 / 0.919 |

Chosen configuration, by category:

| Category     | recall@5 | MRR   |
| ------------ | -------: | ----: |
| preference   |    0.969 | 0.969 |
| filtered     |    1.000 | 1.000 |
| multilingual |    0.857 | 0.750 |

### Findings

- **Both changes help, and they stack.** The model upgrade fixes most of the cuisine and
  multilingual failures; tag boosting fixes the attribute failures ("spicy", "Italian").
- **The smallest boost that works was chosen (0.05).** With e5-base, larger boosts add
  no recall and slightly hurt MRR, and a small boost limits how far lexical matches can
  override semantic similarity.
- **Multilingual queries get no help from tags**, because tags are English (`picante`
  does not match `spicy`). Those gains come from the model alone.
- **e5-small + boost (0.904 / 0.894)** is a reasonable option if the 1.1 GB model is
  too heavy.

### Remaining misses

- `fideos picantes` ranks elote above dan-dan noodles and misses spicy-miso-ramen.
- `quero um prato vegano e picante` misses the green curry and ranks lamb kofta second.
- `algo doce com coco` and `a tropical fruit dessert` rank tiramisu above mango sticky rice.

### Caveats

- **Small and tuned on the same set.** 34 cases, no held-out split: the boost weight was
  picked on the data it is reported on, so the numbers are optimistic.
- **Same author for tags and queries.** Tag boosting benefits from queries that use the
  menu's vocabulary; real users will phrase things differently.

Next steps when the dataset grows: a held-out split, translating or embedding tags for
multilingual matching, and adding real user phrasing to the eval set.

# Answer-quality evaluation

```bash
uv run python -m menu_assistant.eval.answers            # failures only
uv run python -m menu_assistant.eval.answers --cases    # every answer
```

Needs an index and a running Ollama. Every question in
[`data/eval/answer_questions.json`](../data/eval/answer_questions.json) goes through the
real `AnswerService` (retrieval, prompt, LLM, verification), and each reply is scored
with deterministic checks in [`eval/answer_checks.py`](../src/menu_assistant/eval/answer_checks.py).

## Method

22 questions in four categories: taste preferences, restricted (allergens, diets,
explicit filters), multilingual (Portuguese and Spanish), and off-menu (dishes that do
not exist, prices, impossible combinations). Labels are validated against the menu and
the filters the system will apply, so a case cannot reward a dish the filters exclude.

| Check     | Passes when                                                          | Applies to |
| --------- | -------------------------------------------------------------------- | ---------- |
| `cites`   | the **raw** LLM output cites no id the model was not given            | all        |
| `noleak`  | the final text names no menu dish that retrieval did not return      | all        |
| `relev`   | at least one cited dish is labeled relevant                          | cases with relevant dishes |
| `<=3`     | at most 3 dishes are cited (prompt rule)                             | all        |
| `notice`  | the staff notice is present exactly when expected                    | all        |
| `unavail` | the reply says the menu does not have it (EN/PT/ES phrases)          | off-menu   |

`cites` looks at the output *before* citation clean-up, so it measures how often the
model invents ids even though users never see them. `noleak` checks what users do see.
The CLI exits with status 1 only if `notice` fails, because the notice is enforced in
code; the other checks measure model behavior.

**Why rules and not an LLM judge:** the checks are free, fast, reproducible, and test the
exact rules the product promises. A judge model would add cost, variance, and its own
errors, and the local 3B model is too weak to judge itself.

## Results (`llama3.2`, temperature 0.2)

| Group        | cases | pass | cites | noleak | relev | <=3  | notice | unavail |
| ------------ | ----: | ---: | ----: | -----: | ----: | ---: | -----: | ------: |
| preference   |     6 | 100% |  100% |   100% |  100% | 100% |   100% |     n/a |
| restricted   |     6 |  67% |   67% |   100% |  100% | 100% |   100% |     n/a |
| multilingual |     5 |  60% |  100% |   100% |   60% | 100% |   100% |     n/a |
| off_menu     |     5 | 100% |  100% |   100% |   n/a | 100% |   100% |    100% |
| **overall**  |    22 |  82% |   91% |   100% |   88% | 100% |   100% |    100% |

Mean latency was ~1.9 s per question with Ollama on the development machine. Results vary a little
between runs; a first run differed in which restricted cases invented ids.

### Findings

- **Code-side safety holds.** No reply named a dish that retrieval excluded, every notice
  was correct, and every off-menu question was acknowledged (one by the deterministic
  "no match" reply, without calling the LLM).
- **The model invents citation ids** in 2 of 22 replies (`[veggie-stir-fry]`,
  `[green-curry]`). Citation verification removes them, which is why it exists.
- **Portuguese is the weakest area.** "Quero algo apimentado com macarrão" retrieved
  carbonara instead of spicy noodles (tag boost is English-only), and for
  "alergia a amendoim e gergelim" the model wrongly claimed the safe desserts contain
  peanuts, confusing *almond flour* with *amendoim*, and recommended nothing.

### Caveats

- 22 cases, written by the same author as the menu; a single run per configuration.
- Rule-based checks cannot catch every invented detail inside a sentence (e.g. "you can
  ask for extra chili"), judge tone, or verify the reply's language.
- The `unavail` phrase list is a heuristic and can miss unusual wording.
