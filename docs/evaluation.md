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
