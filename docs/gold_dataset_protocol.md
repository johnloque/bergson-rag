# Gold dataset construction protocol

Protocol for manually building the ~50-item annotated query/chunk
evaluation set. Scope: factual and definitional questions only, anchored
in a small, boundable set of chunks — comparative and open-interpretive
questions are out of scope for this project (see docs/ROADMAP.md,
"Scope decision").

## Chunk-first construction

Always start from a chunk you are actively reading — via the chunk
correspondence export (see "Looking up paragraph_ids" below), not from a
question you'd like to ask. Write the query backward from the chunk,
re-reading its full text before drafting anything. Do not rely on
general knowledge of Bergson's doctrine — the dataset checks grounding
against specific corpus text, not against secondary scholarship.

## Looking up paragraph_ids

Ground truth is expressed in `paragraph_ids` (`fix/gold-dataset-paragraph-refs`,
Sprint 11) rather than directly in `chunk_ids`: `chunk_id`s are reassigned
from scratch on every re-chunking run (`src/ingestion/chunking.py`), while
`paragraph_id`s are stable across re-chunking (assigned once at ingestion,
Sprint 1). Annotating against `paragraph_ids` means the gold dataset
survives future chunk-size experiments (Sprint 14) without a by-hand
remap.

Each value is a `paragraph_id` in the exact format `{work_id}_p{number}`
(e.g. `1934_PM_p1`) — the same identifiers produced by ingestion
(Sprint 1), not hand-numbered. Use the chunk correspondence export
(`data/processed/chunks/{work_id}.json`, a flat list of `{chunk_id,
section_path, paragraph_ids, text}`) to find the passage you're
annotating — search/grep against `text`, then copy the `paragraph_id`(s)
from that chunk's `paragraph_ids` list, not the `chunk_id` itself. Do not
guess or reconstruct a `paragraph_id` by hand; use the value exactly as it
appears in the correspondence export.

**Resolution happens at evaluation time, not at annotation time.** The
evaluation scripts (`eval/scripts/run_eval.py`) parse each gold
`paragraph_id` (`src.paragraph_chunk_map.parse_paragraph_id`) and resolve
it to whatever `chunk_id` currently contains it
(`src.paragraph_chunk_map.resolve_chunk_id`, reading
`data/processed/chunks/` as it exists at run time) before scoring against
`/retrieve`'s results. A `paragraph_id` resolves to exactly one `chunk_id`
under any given chunking (chunks are non-overlapping paragraph groups,
Sprint 1) — resolution asserts this rather than silently handling zero or
multiple matches. For `ground_truth_type: multi`, each listed
`paragraph_id` is resolved independently before the "any one counts" (OR)
check, so several `paragraph_id`s resolving to the same or to different
`chunk_id`s both work correctly without special-casing.

## Quotas (n=50)

| Category | Share | Count |
|---|---|---|
| Factual | 60% | 30 |
| Definitional | 40% | 20 |

Cross-cutting, within the above:
- Coverage across all 8 works (at least 4-5 items per work)
- ~6-7 items using contemporary vocabulary in the query while the
  target chunk uses Bergson's own period phrasing (`vocabulary_type:
  modern`)
- 3-5 items where the target chunk contains a quotation Bergson
  explicitly attributes to another author, flagged via
  `footnote_related`
- 8-10 items written in `query_style: keyword` (see below), the rest
  in `query_style: framed`

## Query style: framed vs. keyword

Two registers are both plausible for this project's audience (Bergson
researchers), for a concrete reason: some of them are already users of
search/concordance tools (e.g. TXM) and may transpose that habit here,
at least for part of their queries — not confirmed, but plausible enough
to measure rather than assume away.

- `framed`: a complete natural-language question, as most items already
  are (e.g. "Selon Bergson, pourquoi le langage nous pousse-t-il à...").
- `keyword`: a short search-bar-style query (e.g. "image boule de neige
  perception changement").

**Keyword-style items must be written directly in that register from
the start** — picking the chunk first, then writing the keywords a
researcher would plausibly type to find it — never produced by
mechanically stripping connecting words from an existing `framed` item.
A stripped-down version is not ecologically valid (nobody composes a
query that way) and conflates two different things if it underperforms:
whether keyword phrasing itself is harder to retrieve on, or whether the
dense embedding model simply handles keyword-style input worse because
it is out-of-distribution for a model trained mostly on natural
sentences. Writing keyword items independently avoids this confound.

Do not duplicate a `framed` item into a paired `keyword` variant to
inflate the count — two variants of the same underlying question are
correlated observations, not two independent data points, and would
overstate this dataset's effective sample size. If you want to isolate
the effect of framing later as a dedicated question, that is a separate,
explicitly paired diagnostic set — not part of this gold dataset.

## Single vs. multi ground truth

For every item, ask: would a different chunk, elsewhere in the corpus,
answer this exact query just as correctly?

- **No** — the query is anchored by something specific to this chunk (an
  example, an image, a step in the argument). Ground truth is one
  `paragraph_id` (or, for a chunk spanning several paragraphs, the
  paragraph(s) that anchor the query — any one resolves to the same
  chunk). Prefer this whenever possible: simpler to score, more
  diagnostic when retrieval fails.
- **Yes** — either narrow the query until only one chunk fits, or accept
  a multi-valued ground truth: a set of `paragraph_ids`, any one of which
  (after resolution to a chunk_id) counts as a correct retrieval. Set
  `ground_truth_type` to `multi` in that case. This happens most often
  with definitional items, where Bergson restates a notion equivalently
  at more than one point in the corpus.

If a query only seems answerable by combining several chunks jointly
(not "any one of several"), or by tracing a notion across most of the
corpus rather than a small identifiable set, it is out of scope for this
dataset — see "Out-of-scope items" below.

## Per-item procedure

1. Find a chunk via the correspondence export.
2. Re-read its full text before drafting the query.
3. Write the query so the chunk is necessary to answer it.
4. Decide `query_style` (framed or keyword) — see above, independent
   items only.
5. Apply the single-vs-multi check; search for other equally valid
   chunks if in doubt.
6. Write `expected_answer` as a tight paraphrase strictly bounded by the
   chunk(s) — no additions.
7. Rate `difficulty` (easy/medium/hard) from lexical overlap between the
   query's wording and the chunk's actual vocabulary.
8. Review again after drafting a few other items, to catch answers that
   leaked in general knowledge of Bergson rather than the chunk itself.

## Out-of-scope items

If, while reading, you come across a genuinely interesting question that
turns out to require tracing a notion across most of the corpus (a
recurring image, a concept whose meaning shifts across works), do not
annotate it here. Set it aside in a separate note for the companion
graph-based project — it is a positive signal for that project's own
test cases, not a gap in this dataset.

## Mitigating single-annotator bias

No second annotator means no inter-annotator agreement check. Two
mitigations:
- Time-delayed self-review: re-derive each answer from the chunk alone a
  few days later, without looking at your first draft.
- LLM-assisted adversarial check: have an LLM verify that each cited
  chunk fully entails the expected answer, nothing added or missing — a
  faithfulness check on the gold set itself, not on generated content.

## Schema

```
id, category, query, query_style, ground_truth_type, paragraph_ids,
expected_answer, vocabulary_type, difficulty, footnote_related
```

- `category`: `factual` or `definitional`
- `query_style`: `framed` or `keyword`
- `ground_truth_type`: `single` or `multi`
- `paragraph_ids`: one or more `paragraph_id`s, comma-separated if more
  than one, each in the exact format `{work_id}_p{number}` (e.g.
  `1934_PM_p1`) — `work_id` itself may contain an underscore, so parse
  from the end (`^(.+)_p(\d+)$`), not by splitting on the first
  underscore. Resolved to `chunk_id`(s) at evaluation time, never stored
  as `chunk_id`s directly — see "Looking up paragraph_ids" above.
- `vocabulary_type`: `bergsonian`, `modern`, or `mixed`
- `difficulty`: `easy`, `medium`, or `hard`
- `footnote_related`: `yes` or `no`

## Worked examples

```
id: Q-EXAMPLE-1
category: factual
query: Selon Bergson, pourquoi le langage nous pousse-t-il à juxtaposer
  dans l'espace des phénomènes qui n'occupent pourtant aucun espace ?
query_style: framed
ground_truth_type: single
paragraph_ids: 1888_EDIC_p1
expected_answer: Parce que le langage exige, pour que nous puissions
  nous exprimer par des mots, que nous établissions entre nos idées les
  mêmes distinctions nettes et la même discontinuité qu'entre les objets
  matériels dans l'espace — utile dans la vie pratique et nécessaire
  dans la plupart des sciences, mais source possible de difficultés
  insurmontables pour certains problèmes philosophiques.
vocabulary_type: bergsonian
difficulty: easy
footnote_related: no
```

```
id: Q-EXAMPLE-2
category: definitional
query: image boule de neige perception changement
query_style: keyword
ground_truth_type: single
paragraph_ids: 1907_EC_p13
expected_answer: [tight paraphrase of the chunk's actual content —
  written independently, not derived from Q-EXAMPLE-1's style]
vocabulary_type: bergsonian
difficulty: medium
footnote_related: no
```

## Next wave

50 items are enough for a first working evaluation set. Extend later
only if evaluation results on this first batch show a real need for
more volume, not as a default next step.
