# `judge_chunk` — on-demand per-chunk relevance judgment (Sprint 6)

On-demand LLM relevance judgment for a single chunk: `judge_chunk(query,
chunk, model=DEFAULT_JUDGE_MODEL) -> ChunkJudgment`, in
`src/generation/chunk_judge.py`.

## Singular, not batched

Replaces the plural `judge_chunks(query, chunks)` signature originally
sketched in the roadmap's API-decomposition section — that batched design
was never built (no prior branch, no migration needed). `judge_chunk` judges
exactly one chunk per call.

One chunk in context per call also makes cross-chunk contamination (the
judge's read of chunk B being colored by having seen chunk A in the same
prompt) structurally impossible, rather than a prompt-design precaution a
batched version would have had to build in.

## Judge model choice

`CHUNK_JUDGE_MODEL = "ollama_chat/mistral-nemo"` (`src/generation/chunk_judge.py`,
local 12B via Ollama), also the default of `/judge-chunk`'s `model` field.
It is **a pragmatic baseline, not a validated judge**.

Until `feat/chunk-judge-nemo`, the chunk judge shared the
faithfulness check's `DEFAULT_JUDGE_MODEL` (local mistral 7B). That one
stays the faithfulness judge: it is frozen in `eval/frozen_judge.json`, and
the generation baseline depends on it. Only the chunk judge moved. The
Sprint 6 reason to stay local still holds: the hosted Mistral judge rated
confirmed hallucinations as faithful
([`docs/anti_hallucination_guardrails.md`](anti_hallucination_guardrails.md)).

**Why nemo.** Against the 7B, `judge_chunk` barely discriminated: on 8
(query, chunk) pairs it answered "partiellement pertinent" 7 times. That
included an off-topic chunk (the San Francisco earthquake for Q001's
snowball question) and every gold paragraph of Q007. Nemo, with
`judge_chunk.relevance` v2 unchanged, uses the whole label scale:

| Pair | Expected | mistral 7B | mistral-nemo 12B |
| --- | --- | --- | --- |
| Q010 · `1932_2S_c170` (gold, states the answer verbatim) | pertinent | partiellement | partiellement |
| Q010 · `1907_EC_c382` (retrieval #2) | partiellement / non | partiellement | partiellement |
| Q010 · `1934_PM_c259` (retrieval #3, no geological metaphor) | partiellement / non | partiellement | **pertinent** (false positive) |
| Q001 · `1907_EC_c13` (gold) | pertinent | pertinent | pertinent |
| Q001 · `1932_2S_c115` (off-topic) | non pertinent | partiellement | **non pertinent** |
| Q007 · `1888_EDIC_c1` (gold) | pertinent | partiellement | **pertinent** |
| Q007 · `1934_PM_c45` (gold) | pertinent | partiellement | **pertinent** |
| Q007 · `1934_PM_c68` (gold) | pertinent | partiellement | partiellement |

`temperature=0`, `num_ctx=16384` (the longest prompt is 1,118 tokens), 3
identical repeats per pair, 2026-10-19. The choice is pragmatic. Nemo is
not shown to be more *reliable*. It behaves more like a judge is expected
to: its label depends on the chunk instead of defaulting to the middle of
the scale. A judge that always says "partiellement pertinent" carries no
signal at all.

**Known limits, unchanged or new with nemo:**

- **Literal reading.** On Q010's gold chunk, the 7B and nemo both claim the
  chunk "ne mentionne pas explicitement la métaphore géologique". The judge
  looks for the question's words rather than its meaning. Neither a shorter
  excerpt (97 words) nor the metaphor moved first changed that on the 7B.
  Nor did the two prompt variants tried: justification before label in the
  JSON, and an instruction to judge by meaning.
- **False positives.** Nemo is more decisive in both directions. It calls
  `1934_PM_c259` "pertinent" because it reads the rarefaction of air as a
  geological image.
- **Thinner justifications.** Nemo can give one sentence restating the
  question ("L'extrait utilise explicitement l'image de la boule de neige
  pour décrire la perception du changement…") where the prompt asks for 2–4
  sentences grounded in the chunk. The 7B passed
  `test_judge_chunk_justification_is_not_generic_boilerplate`. Nemo fails
  it, so that test is a non-strict xfail: a known limit of this baseline.
- **Not an evaluation.** 8 pairs, no ground truth for the retrieval #2/#3
  chunks. At `temperature=0` the repeats are not independent samples, so
  "3/3" means deterministic, not stable.
- **Model swaps.** On a 16 GB machine, Ollama can't keep mistral
  (generation, faithfulness) and nemo (chunk judge) loaded together. Every
  switch between `/generate` and `/judge-chunk` reloads a model, in both
  directions. Measured on a 1-token call (2026-10-19, M-series Mac, 16 GB):
  `/generate` → `/judge-chunk` 9–11 s (nemo, 7.2 GB, `num_ctx=16384`),
  `/judge-chunk` → `/generate` 3.7–3.9 s (mistral, 4.7 GB). The tests'
  reachability ping for nemo waits 60 s for that reason. This is not new
  to nemo: Ollama also reloads a model when `num_ctx` changes, so
  `/generate` (Ollama's default context) ↔ `/evaluate` (`num_ctx=16384`)
  already cost 3.3–3.6 s each way on mistral alone.

**A baseline for future experiments, which remain to be run.** No
evaluation strategy exists for this feature yet: `judge_chunk/*` is
excluded from the prompt-variant tooling because there is no ground truth
(`docs/prompts.md`). Nemo + v2 is the reference that any of the following
would be measured against:

- a labelled set of (query, chunk, expected label) pairs, the prerequisite
  for comparing anything beyond a handful of hand-picked cases;
- a hosted, larger judge (`mistral/mistral-small-latest` could not be tried:
  the API key returned 429 on every call);
- prompt changes targeting the literal reading (e.g. asking the judge to
  first quote the passage that answers, if any) and the justification
  length;
- the task's shape: the three-level scale, a single verdict per call.

Not a RAGAS metric: `check_faithfulness` already covers claim-vs-evidence
entailment via `ragas.metrics.Faithfulness`. This is a distinct
query-vs-chunk relevance judgment with its own, project-specific discrete
label set (`ChunkJudgmentLabel` — pertinent / partiellement pertinent / non
pertinent, not a numeric score — consistent with this project's general
preference for discrete tiers over false-precision numbers on judge-adjacent
signals, e.g. `RetrievalConfidenceTier` in `src/generation/signals.py`), so a
hand-written prompt plus a direct `litellm.completion` call is used instead
of forcing it through a RAGAS metric shaped for a different question.

## JSON parsing, with one retry

The local 7B judge (the chunk judge's model until nemo replaced it, see
above) is the same model `src/generation/faithfulness.py` documents as prone
to producing free-text instead of well-formed JSON under context pressure (RAGAS needed its own internal fix-the-format retry for the
same failure mode against the same model). `judge_chunk` asks for a single
JSON object in the prompt (no `response_format` forcing — not all LiteLLM
providers support it uniformly, and this project has no established need for
it elsewhere) and retries once, with a corrective follow-up message, if the
first response doesn't parse as the expected object.

## Output contract

Conforms to the `ChunkJudgment` contract already committed in
`src/generation/chunk_judgment.py` ahead of this branch, in Sprint 6 (see
[`docs/anti_hallucination_guardrails.md`](anti_hallucination_guardrails.md)):

```python
ChunkJudgment = {"label": "pertinent" | "partiellement pertinent" |
                 "non pertinent", "justification": str}
```

`generate_from_chunks` needed no changes — it already accepted this shape.

## Deferred to Sprint 7

- **Accumulation.** Turning repeated `judge_chunk` calls into the
  `chunk_judgments: dict[str, ChunkJudgment]` shape `generate_from_chunks`
  accepts is a frontend/client-side responsibility. This module has no
  dict-shaped entry point of its own.
- **Persistence.** Durable storage of judgments across sessions (SQLite, per
  the Sprint 7 plan) is a separate, still-deferred concern — this branch has
  no persistence layer at all, in-memory or otherwise.

## Test coverage

`tests/test_chunk_judge.py`:
- `test_judge_chunk_pertinent_for_matching_chunk` /
  `test_judge_chunk_non_pertinent_for_unrelated_chunk` — label correctness
  against a matching chunk (Q010's gold chunk, which states the answer
  verbatim) vs. an unrelated one. Both are non-strict xfails: the pertinent
  one still fails with nemo (literal reading, above).
- `test_judge_chunk_justification_is_not_generic_boilerplate` — the
  justification cites something concrete from the chunk, not a
  templated/generic sentence. Non-strict xfail with nemo (thinner
  justifications, above).
- `test_judge_chunk_output_feeds_generate_from_chunks` — a `judge_chunk`
  output, wrapped in the `chunk_judgments` dict shape, is accepted unmodified
  by `generate_from_chunks`.
