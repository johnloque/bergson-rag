# Chatbot RAG — Complete works of Henri Bergson

## Scope decision

Rationale, reached after an empirical check
against real Bergson secondary literature: doctrinal/conceptual
questions ("what is Bergson's theory of X") tend to be anchored in one
canonical text and are well served by top-k retrieval + synthesis;
recurring-image questions and questions about concepts whose meaning
shifts across the corpus tend to be genuinely dispersed and are not
reliably solved by this architecture, regardless of prompt design —
documented multi-document aggregation and long-context reliability
limits apply, not just a context-window-size problem. This class of
question is the subject of a separate, complementary project (graph
propagation over a paragraph graph and a lexicon graph), not of
bergson-rag.

## Validated architecture decisions

- **Source data**: single source (`raw/src`, paragraph-level XML) rather
  than two aligned sources. Paragraph IDs are assigned automatically at
  ingestion time, making the corpus its own single source of truth for
  paragraph identity — no cross-file alignment, no dependency on
  `tag/src`'s existing numbering. Lemma and POS annotations are
  regenerated at indexing time with a current spaCy model rather than
  reused from the 5-year-old `tag/src` encoding. This also makes three
  previously logged data-quality issues on `bergson-synoptique` (POS
  `nan` values in 1919_ES, inconsistent apostrophes in 1907_EC, no
  shared paragraph identifier between sources) non-blocking for this
  project — they remain valid to fix on `bergson-synoptique` for other
  uses (TXM, in particular), just no longer a dependency here.
  A prior manual POS correction pass exists for the `possible`/`virtuel`
  lemmas specifically (from earlier master's research) — too narrow in
  scope to justify keeping the old encoding as this project's source of
  truth, but preserved as an asset for the companion graph project's
  validation case study.
- **Text normalization for retrieval — two separate pipelines, not one**:
  - Lemmatization (spaCy, current model, version-pinned in
    `pyproject.toml`) — produces the canonical dictionary form used for
    display, the MCP exact-lemma lookup tool, and the lexicon graph in
    the companion project. Linguistically motivated, not a retrieval
    optimization.
  - Stemming (French Snowball / Savoy algorithm, via the
    `snowballstemmer` package) — used specifically to build the BM25
    sparse index. Rule-based suffix stripping, not a trained model:
    more robust to period-specific (1889–1932) French than a
    lemmatizer trained on contemporary text, and directly addresses the
    morphological-variant conflation that a lemmatizer can miss.
  - Whether stemming or spaCy lemmas produce better BM25 recall on this
    specific corpus is not assumed — validated empirically via an `exp/`
    branch in Sprint 2–3 against the gold dataset, same discipline as
    other retrieval choices in this project.
- **Chunking**: hierarchical (parent/child), leveraging the existing XML
  structure. A separate positional neighborhood-window mechanism was
  considered and dropped: the parent context already covers the
  "explanatory passage 2–3 paragraphs away" case within the anchored
  scope this project now targets.
- **Retrieval**: hybrid BM25 (on lemmas) + dense (BGE-M3), fused via RRF.
  Corpus-trained FastText query expansion was considered and dropped —
  it targeted vocabulary drift on the kind of broad/exploratory question
  now out of scope.
- **Query reformulation**: dropped from default scope, not deferred as a
  placeholder — the query is used as-is, raw, with no LLM rewrite,
  synonym enrichment, or decomposition. It remains a documented `exp/`
  candidate, revisited only once a larger gold dataset can actually
  measure whether it helps, not built into the default pipeline.
- **Discourse-framing noise in dense queries**: keyword-extraction or
  stopword/framing-noise filtering ahead of the dense embedder was
  considered and deliberately not hand-built. The gold dataset already
  carries `query_style` (`framed` vs. `keyword`) and `vocabulary_type` as
  dimensions specifically so this question is measured via retrieval
  breakdowns once enough annotated items exist, rather than answered by
  introducing a manually curated keyword/stopword list — consistent with
  this project's general preference for data-driven validation over
  manual curation (see stemming vs. lemmas for BM25, above).
- **Scoring**: cross-encoder reranker (bge-reranker-v2-m3) as the
  default, always-on relevance score. A separate, on-demand LLM relevance
  judgment (`judge_chunks`) provides a short textual justification per
  chunk, computed only when the user requests it. Kept deliberately: it
  is what makes answer fidelity checkable by a non-specialist reviewer,
  a central argument for staying on the Bergson corpus at all.
- **Generation**: single synthesis mode over a small, bounded evidence
  set, with mandatory citations. No evidence-conditioned branching by
  question category — not needed once evidence sets are consistently
  small by construction.
- **Anti-hallucination guardrails**: post-generation validation layer +
  mandatory citations; generated syntheses are treated as interpretive
  proposals to verify, not as definitive answers.
- **API decomposition**: three independent endpoints —
  - `retrieve(query)` — hybrid search + reranking, returns chunks
  - `generate_from_chunks(query, chunks)` — synthesis from a given,
    possibly user-curated, chunk selection
  - `judge_chunks(query, chunks)` — on-demand relevance judgment
    (score + justification) per chunk
- **Infra**: Qdrant (dense + sparse), FastAPI, Docker Compose as the
  reference setup. Kubernetes is not built — a one-line note on the
  natural scaling path suffices for this demo, not a dedicated sprint.
- **MCP**: pure search tool (no generation), exposing hybrid search and
  exact-reference lookup. Lowest priority of the remaining scope — the
  first thing to cut if time runs short before target interview dates.

## Evaluation methodology

Outcome-based only, given the reduced scope: ground truth = one or more
`(work, paragraph_id)` pairs (`ground_truth_type: single` or `multi`,
where `multi` means any one of several valid passages suffices — no
AND/OR sub-typing, judged not worth the added complexity at this
project's scale). Metrics: recall@k, MRR, faithfulness, context
precision/recall (RAGAS).

Full annotation protocol: `docs/gold_dataset_protocol.md` — pending the
follow-up pass noted in "Status" above to drop the
comparative/contested quotas.

## Sprint breakdown

Each sprint targets 1–2 weeks of part-time work and ends with a
demonstrable deliverable. From Sprint 3 onward, each sprint closes with
a measured metric, not just "it works".

### Sprint 0 — Scoping and foundations
Data schema audit, copyright confirmation, gold dataset construction,
dev environment setup.

### Sprint 1 — Ingestion and chunking
Parse `raw/src` XML into structured objects, auto-assign paragraph IDs
at ingestion (single source of truth, no cross-file alignment needed),
hierarchical chunking. Unit tests on chunk boundaries and on paragraph
ID assignment stability (re-running ingestion on an unchanged corpus
must not renumber paragraphs).

### Sprint 2 — Hybrid indexing
Qdrant setup, single collection with two named vectors per point (dense
BGE-M3 + sparse BM25). Text normalization: spaCy lemma+POS generation
(canonical form, used outside the BM25 index — stored but not indexed
this sprint) and French Snowball stemming (used for the BM25 index
specifically) as two separate outputs of the same indexing step
(`src/indexing/normalize.py`). BM25 input is isolated behind a single
`bm25_input()` seam so switching it from stems to lemmas later is a
small change, not a rewrite.

**Deferred, not skipped**: the `exp/` branch comparing BM25-on-stems vs
BM25-on-spaCy-lemmas (recall@k against the gold dataset) did not happen
in Sprint 2 as originally planned here — the gold dataset and a working
retrieval/eval loop (Sprint 3) are prerequisites for a meaningful
recall@k comparison. Moved to a later sprint, once retrieval and
evaluation exist. Sprint 2 ships with stemming as the BM25 default in
the meantime (rationale: rule-based, more robust to period-specific
1889-1932 French than a lemmatizer trained on contemporary text,
established IR practice for French).

### Sprint 3 — Hybrid retrieval
RRF fusion over the raw, un-reformulated query. First retrieval-only
evaluation (recall@k, MRR, comparison between dense & sparse channels).

### Sprint 4 — Reranking
Cross-encoder integration. Retrieval-only evaluation (recall@k, MRR, results comparison with hybrid retrieval)

**Reranking — implemented.** Cross-encoder reranking (`bge-reranker-v2-m3`)
in `src/retrieval/reranking.py`, callable independently of
`src/retrieval/hybrid.py`. `eval/scripts/run_reranking_comparison.py`
generates the before/after recall@k/MRR report on `eval/gold_dataset.csv`
(n=10) directly from this retrieval path:
[`eval_reranking_n10_20260816T122756Z.md`](../eval/results/eval_reranking_n10_20260816T122756Z.md).

**Deferred, not skipped**: BGE-M3 multi-vector (ColBERT-style) reranking,
gated on two unmet conditions — (1) a feasibility check of extracting
colbert vectors in this stack, likely requiring `FlagEmbedding` (not added
this sprint), and (2) a larger gold dataset, needed for a meaningful
reranker-vs-reranker comparison. Revisit once both are met
(`docs/gold_dataset_protocol.md`).

### Sprint 5 - LLM Integration

Single-mode prompt design, LLM integration (local + API fallback),
preliminary end-to-end evaluation (RAGAS).

**LLM integration — implemented.** `generate_from_chunks` in
`src/generation/generate.py`, via LiteLLM (Mistral/Ollama local default,
Mistral hosted API fallback). Evidence-conditioned prompt, mandatory
citations, Test A/B coverage in `tests/test_generation.py`.
Anti-hallucination guardrails implemented in Sprint 6, below; `judge_chunks`
remains its own, later branch.
Full design rationale: [`docs/generation_strategy.md`](generation_strategy.md).

**RAGAS evaluation — implemented.** `eval/scripts/run_ragas_eval.py`
(`generation_only` and `end_to_end` modes; faithfulness, context precision,
context recall) against a local or API judge LLM, with an explicit two-run
determinism check. Latest result: [`eval/results/`](../eval/results/)
(exploratory, n=10, below the n=50 protocol target). Full methodology,
the shared faithfulness implementation, and Sprint 6 handoff notes:
[`docs/ragas_evaluation.md`](ragas_evaluation.md).

### Sprint 6 — Anti-hallucination guardrails

Post-generation validation, citation formatting.

**Scope decision, superseding the line above.** Two designs were
considered and dropped before landing on the one actually built:

- **A hard refusal** (an explicit "no reliable answer" response) — dropped.
  `generate_from_chunks` always generates and always returns an answer,
  regardless of retrieval confidence or the faithfulness score computed on
  it afterward. Generated syntheses are already treated as interpretive
  proposals to verify, not definitive answers (this doc's "Validated
  architecture decisions"); a refusal doesn't fit that framing and removes
  a citable, checkable answer the user could otherwise inspect.
- **A separate pre-generation blocking gate** (deciding not to generate at
  all below some confidence threshold) — dropped for the same reason, plus
  a second one: retrieval confidence and generation faithfulness are
  measured independently and don't move together (confirmed by this
  sprint's own test fixtures — Q001/Q004 have a fine, correctly-retrieved
  gold chunk but a hallucinated answer; Q009 has a genuinely poor retrieval
  but the model still declines to fabricate). Gating on retrieval alone
  would have blocked good-faithfulness answers and let some hallucinations
  through untouched.

**What was built instead: presentation-only gating, unified into one
mechanism.** The first generated answer — initial or a manual regeneration —
is always rendered collapsed by default, unconditionally. It auto-expands
only once a post-generation evaluation comes back positive on both an
independent structural/faithfulness check and a retrieval-confidence read.
The user can always expand it manually regardless. This sprint builds the
decision logic and the data it depends on; the actual collapsed-by-default
rendering and persistence of the evaluation result are **deferred to Sprint
7** (see risk note below).

**Implemented**, all in `src/generation/`:

- `generate_from_chunks` (`generate.py`) gains an optional `chunk_judgments`
  parameter — unaffected existing behavior when `None` (Test A from Sprint 5
  still calls it that way). When populated, each judged chunk's label and
  justification are rendered inline with that chunk's evidence text in the
  prompt (`prompt.py`), as an additional signal — not a filter; the caller
  is expected to have already excluded chunks before calling.
- `generate_evaluation(query, chunks, answer) -> EvaluationResult`
  (`guardrail.py`), run after any `generate_from_chunks` call, identically
  for an initial generation and a manual regeneration:
  - **Layer 1**, `check_structure` — deterministic, no LLM call: every
    `[chunk_id]` citation in the answer must resolve to a chunk actually
    passed in, and at least one citation must be present. Carried on
    `EvaluationResult` for the caller/UI, but **not** wired into
    `should_auto_expand`'s own gate (see next point) — the local generation
    model was found, empirically, to often omit citations even from
    well-grounded answers, which would make the gate practically
    unreachable if citation presence were required.
  - **Layer 2**, `check_faithfulness` (`faithfulness.py`, unchanged
    call site, extended return type) — the one LLM call this function
    makes. `check_faithfulness` now also returns RAGAS's per-claim verdicts
    (`FaithfulnessResult.claims`), not just the aggregate score, obtained by
    calling the metric's own two internal steps directly instead of
    `single_turn_score()` — the same two LLM calls, not a second pass —
    so a guardrail can name *which* claim is unsupported.
  - **Retrieval confidence tier**, `signals.retrieval_confidence_tier` —
    imported directly from `src/generation/signals.py`, not reimplemented
    here: the exact same signal Sprint 5's `EvidenceSignals.is_confident`
    already computes, mapped to four tiers (très faible / faible / moyenne
    / élevée) instead of Sprint 5's binary confident/not-confident split.
    One shared definition for both sprints, not two independently-tuned
    ones — see the correction note below for why this needed revisiting
    after this sprint's first pass.
- `should_auto_expand(evaluation) -> bool` (`guardrail.py`): true only if
  retrieval confidence is at least "moyenne" (`signals.CONFIDENT_TIERS`) and
  Layer 2 flagged no unsupported claim.

**Correction, made within this same sprint, before merge: the retrieval
confidence signal was originally a reused-as-is copy of Sprint 5's
coefficient of variation (CV) of cross-encoder rerank scores, mapped to
four tiers with an *inverted* polarity from Sprint 5's own
`CONFIDENCE_CV_THRESHOLD` (lower CV read as higher confidence here, the
opposite of Sprint 5's higher-CV-is-confident reading).** That inversion
was a real inconsistency, not just a documentation nuance — the same named
statistic meant opposite things depending on which module read it. Root
cause: CV is scale-free and a function of the whole candidate set's
composition, not of how good the single best piece of evidence actually is.
Sprint 5 only ever needed a *relative* discrimination question ("does the
reranker prefer one candidate over the others, among already-plausible
chunks") where higher spread legitimately reads as more confident. Sprint 6
needs an *absolute* question ("is there real evidence here at all"), and in
that regime CV misleads: a genuine retrieval miss (near-zero scores across
the board) inflates CV, because tiny absolute differences between near-zero
numbers balloon their *relative* spread, while a real relevant cluster of
scores sits close together in absolute terms and reads as *low* CV — the
opposite of what "low CV = uncertain" would suggest.

Fixed by replacing CV with the single highest cross-encoder score among the
chunks (not their spread) as the shared primitive behind both
`EvidenceSignals.is_confident` (Sprint 5) and `retrieval_confidence_tier`
(Sprint 6, the one public function both now go through) — one definition
(`src/generation/signals.py`), no polarity flip needed anywhere, and
well-defined for a single chunk (no `None`-defaulting edge case CV needed).
This also let `CAUTION_INSTRUCTION` (`prompt.py`) drop its "flat or
non-discriminating" framing, which was already a slightly imprecise trigger
for what Sprint 5 actually wanted (flat-but-uniformly-high scores don't
warrant caution; a low best score does, regardless of spread). Calibrated
against real `bge-reranker-v2-m3` scores on gold_dataset.csv items, not fit
as a formal sweep (see `src/generation/signals.py` for the specific cut
points and numbers) — same "documented placeholder, revisit with a larger
gold dataset" discipline as this project's other thresholds.
- **No second LLM call for the guardrail decision.** A small judge
  calibration (n=4: Q001/Q004 confirmed hallucinations, Q006/Q008 confirmed
  faithful) found the hosted Mistral judge rates the confirmed
  hallucinations as faithful (0.857–0.929) — a second opinion from it could
  overturn a correct local-judge signal in exactly the wrong direction, so
  `generate_evaluation` only ever calls the local 7B judge, once per
  generated answer. This was a small manual check, not a formal before/after
  metrics run against the full gold dataset — reported honestly as such,
  not withheld; a proper before/after comparison needs the larger dataset
  this project is still short of (see gold-dataset-volume notes elsewhere
  in this doc).
- **No auto-correction loop** (generate → critique → revise) — rejected in
  favor of user-initiated regeneration via `chunk_judgments` instead.

**`chunk_judgments` — committed interface contract.** `judge_chunks`
itself is out of scope for this branch (its own, later branch) — this
sprint only builds the consumer side. The shape it must conform to is
fixed now, in `src/generation/judgment.py`:

```python
ChunkJudgment = {"label": "pertinent" | "partiellement pertinent" |
                 "non pertinent", "justification": str}
# generate_from_chunks(..., chunk_judgments: dict[str, ChunkJudgment] | None)
```

Tested against a hand-constructed fixture (`tests/test_guardrail.py`), not
a real `judge_chunks` call, since one doesn't exist yet — this is the target
that branch's output must match, not a placeholder expected to drift.

**Deferred to Sprint 7, with a concrete risk.** UI rendering (the actual
collapsed/auto-expanded badge) and backend persistence of the evaluation
result are both out of scope here — this sprint only builds the decision
logic (`generate_evaluation`, `should_auto_expand`) and its inputs. Risk
this defers: `generate_evaluation` runs after generation completes, not
before it's shown, and nothing persists its result yet — a user who
navigates away or closes the session before `generate_evaluation` finishes,
or before a session is persisted, never sees the answer's final
expanded/collapsed badge state. Sprint 7 needs to close this gap, not just
add the rendering.

Test coverage: `tests/test_guardrail.py` — Q001/Q004 hand-crafted
confirmed-hallucination fixtures (Layer 2 flags the specific fabricated
claim, `should_auto_expand` false despite fine retrieval confidence), Q008
(answer generated and returned unmodified regardless of evaluation outcome),
Q009 (real hybrid_search+rerank pipeline, a genuine persistent miss — très
faible tier, `should_auto_expand` false), Q002 (strong case, auto-expands),
a hand-crafted Layer 1 unknown-citation case, the `chunk_judgments` prompt-content
check, and a manual-regeneration case reusing the Q001 fixture logic against
a `chunk_judgments`-populated `generate_from_chunks` call.

### Sprint 7 — Backend API and persistence
- Three-endpoint FastAPI (`retrieve` / `generate_from_chunks` /
  `judge_chunks`)
- API-level tests (no UI yet)
- SQLite persistence as fast-follow, not a blocker for this sprint's
  deliverable
- **Deliverable**: fully functional, tested API, usable independently of
  any frontend

### Sprint 8 — Frontend
- React (Vite) + Tailwind + TanStack Query, consuming the Sprint 7 API
- Inspect → explain → curate → regenerate loop
- **Deliverable**: working UI against the real API, demoable locally

### Sprint 9 — Integration and bootstrap
- Full dockerization (API, frontend, Qdrant) via Docker Compose
- Bootstrap script/Makefile chaining fetch-data → build-index → run
- **Deliverable**: entire application launchable locally in one command

### Sprint 10 — MCP layer
Pure search tools (hybrid search, exact-reference lookup), tested with
an MCP client. First to drop if time is constrained.

### Sprint 11 — Portfolio polish
Complete README, "Known limitations & scope" section finalized,
evaluation results presented clearly, technical blog post, accessible
demo, curated set of demo questions drawn from the gold dataset for live
presentation.

## Target repo structure

```
bergson-rag/
├── data/
│   ├── raw/              # source XML (gitignored, fetched via script)
│   └── processed/        # chunks, index
├── docs/                 # audits, methodology notes
├── scripts/
│   └── fetch_corpus.sh   # sparse-checkout of the corpus repo
├── src/
│   ├── ingestion/         # XML parsing, chunking
│   ├── indexing/          # BM25, embeddings, Qdrant
│   ├── retrieval/         # reformulation, hybrid, reranking
│   ├── generation/         # prompts, anti-hallucination validation
│   └── mcp_server/         # Sprint 10
├── frontend/               # React (Vite) UI — Sprint 8
├── eval/
│   ├── gold_dataset.csv
│   └── scripts/           # RAGAS, recall@k, etc.
├── docker-compose.yml
├── Makefile                # quickstart target (Sprint 9)
└── pyproject.toml
```
