# LLM generation strategy (Sprint 5)

**LLM integration — implemented.** `generate_from_chunks(query, chunks, client,
model=DEFAULT_MODEL, fallback_model=None)` in `src/generation/generate.py`:
synthesis from a caller-provided chunk selection only — it never calls
retrieval itself, so it works standalone with a hand-constructed chunk list
as well as with real retrieve+rerank output. Multi-provider access goes
through LiteLLM (pinned in `pyproject.toml`) rather than hand-rolled
provider-switching. Default model: Mistral via Ollama
(`ollama_chat/mistral`, local). Default API fallback: Mistral's hosted API
(`mistral/mistral-small-latest`, `DEFAULT_FALLBACK_MODEL`), reading
`MISTRAL_API_KEY` from the environment — chosen over a paid provider
(Anthropic, OpenAI) to keep the default configuration cost-free on
Mistral's free tier. `BERGSON_LLM_FALLBACK_MODEL` overrides it with any
other LiteLLM model string, that provider's API key then being
optional/user-supplied, not activated by default. `model`
is a parameter on each call, not a global setting: the same query/chunks
can be regenerated against a different model without touching any other
code path (parameter-level support only — a side-by-side multi-model
comparison UI is a later frontend task, not this sprint's scope).

## Evidence-conditioned prompt

One template (`src/generation/prompt.py`), dynamically conditioned by
`src/generation/signals.py` on three signals computed purely from the input
chunks — no branch-specific separate templates:

1. Number of distinct works (`EvidenceSignals.is_multi_work`) — continuous
   presentation for one work; grouped-by-work context with explicit
   per-work attribution instructions for several.
2. Evidence convergence (`EvidenceSignals.is_convergent`) — mean pairwise
   cosine similarity over the chunks' dense (BGE-M3) vectors, read back
   from Qdrant (`fetch_dense_vectors`) rather than recomputed, so this
   signal costs no extra embedding call. High convergence: direct
   synthesis instruction. Low: present passages separately, never frame
   the answer as consensus.
3. Reranking confidence (`EvidenceSignals.is_confident`) — coefficient of
   variation of the input chunks' cross-encoder scores. Flat/low spread:
   instruct the model to phrase the answer with epistemic caution. This is
   a soft, prompt-level reaction only — not a hard gate.

`CONVERGENCE_THRESHOLD` / `CONFIDENCE_CV_THRESHOLD` (`src/generation/signals.py`)
are generic, documented placeholders, deliberately **not** fit against
`eval/gold_dataset.csv` — at n=10 the dataset is far below the volume this
project already treats as a threshold for that kind of calibration (same
discipline as the Sprint 4 reranker-vs-reranker deferral). Revisit
once a larger annotated set exists.

Mandatory in every generated answer regardless of branch: explicit
citations to the source chunk_id(s), and framing as an interpretive
synthesis to verify against the cited passages — never a settled,
definitive conclusion.

## Deferred, not skipped

- Anti-hallucination guardrails (post-generation validation, explicit "no
  reliable answer" refusal) — Sprint 6. This sprint's `EvidenceSignals`
  only soften phrasing at the prompt level; nothing here declines to
  answer or validates what the model actually produced.
- `judge_chunks` (on-demand, per-chunk LLM relevance judgment) — deferred
  to its own dedicated commit with its own consigne, not stubbed here.

## Testing approach

Two distinct kinds, reusable for future generation work, not a one-off for
this sprint (`tests/test_generation.py`):

- **Test A — isolated prompt-branch tests.** Call `generate_from_chunks`
  (or, for the LLM-independent tier, `compute_signals`/`build_prompt`
  directly) with hand-fixed chunk sets, no retrieval involved. Assert the
  prompt actually contains the expected conditioning instructions for each
  branch — not just that generation completes without error. Uses Q007's
  corrected chunk set for the multi-work convergent branch, a single gold
  chunk for the mono-work branch, and a constructed (synthetic, clearly
  labeled as such) divergent-evidence pair for the divergence branch, since
  real contested-evidence examples are scarce now that comparative
  questions are out of scope.
- **Test B — pipeline-realistic tests.** Run `generate_from_chunks` on
  whatever the real retrieve+rerank pipeline actually returns for a few
  real gold dataset queries — not the curated gold `chunk_ids` — so the
  candidate set can include a mediocre distractor alongside a good chunk,
  the realistic production case especially while no guardrail exists yet
  to filter it.

Both categories require Qdrant populated; the LLM-calling tests
additionally require a reachable model (Ollama running locally with
`mistral` pulled, or `MISTRAL_API_KEY` set for the default fallback, or
`BERGSON_LLM_FALLBACK_MODEL` set to a different provider with its own API
key configured) and skip cleanly otherwise, same discipline as this repo's
other infra-dependent suites.

## RAGAS evaluation

The "preliminary end-to-end evaluation (RAGAS)" named in Sprint 5's original
scope line is implemented in a later pass on this branch:
`eval/scripts/run_ragas_eval.py` (faithfulness, context precision, context
recall; generation-only and end-to-end modes, reported separately) and
`src/generation/faithfulness.py` (`check_faithfulness` — the reusable
faithfulness function both this eval harness and Sprint 6's future
guardrail will call). Full rationale, including the RAGAS
single-instance-vs-batch API investigation and the `ragas`/`langchain-community`
version pin: `docs/ROADMAP.md`'s Sprint 5 section and the module docstrings
in both files above.
