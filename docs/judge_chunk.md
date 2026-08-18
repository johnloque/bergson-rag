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

Same default judge as `generate_evaluation`'s faithfulness check
(`DEFAULT_JUDGE_MODEL`, `src/generation/faithfulness.py` — local 7B via
Ollama by default). The Sprint 6 judge calibration
([`docs/anti_hallucination_guardrails.md`](anti_hallucination_guardrails.md))
found the hosted Mistral judge rates confirmed hallucinations as faithful, so
the local judge is preferred wherever a judge-shaped decision is made in this
project — no established reason to pick a different judge for this adjacent
signal.

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

The local 7B judge is the same model `src/generation/faithfulness.py`
documents as prone to producing free-text instead of well-formed JSON under
context pressure (RAGAS needed its own internal fix-the-format retry for the
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
  against a matching vs. an unrelated chunk.
- `test_judge_chunk_justification_is_not_generic_boilerplate` — the
  justification cites something concrete from the chunk, not a
  templated/generic sentence.
- `test_judge_chunk_output_feeds_generate_from_chunks` — a `judge_chunk`
  output, wrapped in the `chunk_judgments` dict shape, is accepted unmodified
  by `generate_from_chunks`.
