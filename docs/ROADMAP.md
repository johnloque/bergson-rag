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
  judgment (`judge_chunk`, one chunk per call — see Sprint 6) provides a
  short textual justification per chunk, computed only when the user
  requests it. Kept deliberately: it is what makes answer fidelity
  checkable by a non-specialist reviewer, a central argument for staying
  on the Bergson corpus at all.
- **Generation**: single synthesis mode over a small, bounded evidence
  set, with mandatory citations. No evidence-conditioned branching by
  question category — not needed once evidence sets are consistently
  small by construction.
- **Anti-hallucination guardrails**: post-generation validation layer +
  mandatory citations; generated syntheses are treated as interpretive
  proposals to verify, not as definitive answers.
- **API decomposition**: four independent functions, each exposed as its
  own HTTP endpoint by the Sprint 7a FastAPI service (`src/api/`) —
  - `retrieve(query)` — hybrid search + reranking, returns chunks
    (`POST /retrieve`)
  - `generate_from_chunks(query, chunks)` — synthesis from a given,
    possibly user-curated, chunk selection (`POST /generate`)
  - `generate_evaluation(query, chunks, answer)` +
    `should_auto_expand(...)` — post-generation anti-hallucination
    evaluation (see Sprint 6), a separate call from generation itself so
    the client can render the draft answer immediately and only apply the
    collapsed/auto-expand decision once evaluation resolves
    (`POST /evaluate`)
  - `judge_chunk(query, chunk)` — on-demand relevance judgment (label +
    justification) for a single chunk; called once per chunk, not
    batched (see Sprint 6) (`POST /judge-chunk`)

  Sprint 7a shipped these four endpoints with no persistence and no
  session/conversation history: each request was self-contained, and a
  known, deliberately unresolved simplification followed directly from
  that. Sprint 7b (`feat/api-persistence`) adds SQLite persistence
  (`src/api/models.py`) and two read endpoints (`GET /turns/{id}`,
  `GET /conversations/{id}`) that close it — see Sprint 7's own write-up
  below.
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

**Guardrails — implemented.** Presentation-only gating, not a generation
refusal or a pre-generation blocking gate: the first generated answer is
always rendered collapsed by default, and auto-expands only once a
post-generation evaluation (`generate_evaluation` in
`src/generation/guardrail.py`) confirms both an independent
structural/faithfulness check and a sufficient retrieval-confidence tier.
The user can always expand it manually. UI rendering and persistence of
the evaluation result are deferred to Sprint 7.
Full design rationale, the CV→best-score confidence-signal correction, and
Sprint 7 handoff notes:
[`docs/anti_hallucination_guardrails.md`](anti_hallucination_guardrails.md).

**`judge_chunk` — implemented.** `judge_chunk(query, chunk, model=DEFAULT_JUDGE_MODEL)
-> ChunkJudgment` in `src/generation/chunk_judge.py`: an on-demand relevance
judgment (label + justification) for one chunk per call. Accumulation into
the `chunk_judgments` dict and persistence across sessions remain deferred
to Sprint 7. Full design rationale, judge-model choice, and test coverage:
[`docs/judge_chunk.md`](judge_chunk.md).

### Sprint 7 — Backend API and persistence
- Four-endpoint FastAPI (`retrieve` / `generate` / `evaluate` /
  `judge-chunk`)
- API-level tests (no UI yet)
- SQLite persistence as fast-follow, not a blocker for this sprint's
  deliverable
- **Deliverable**: fully functional, tested API, usable independently of
  any frontend

**Implemented (Sprint 7a `feat/api-endpoints` + Sprint 7b
`feat/api-persistence`).** FastAPI scaffold in `src/api/`, each endpoint a
thin wrapper around an existing, already-tested function, plus SQLite
persistence (conversations, turns, retrieved chunks, generations,
evaluations, chunk judgments) closing two risks flagged as deferred in
prior sprints. Full design rationale, schema, and test coverage:
[`docs/backend_api.md`](backend_api.md).

### Sprint 8 — Frontend
- React (Vite) + Tailwind + TanStack Query, consuming the Sprint 7 API
- Inspect → explain → curate → regenerate loop
- **Deliverable**: working UI against the real API, demoable locally

**Implemented.** React 19 + Vite + Tailwind v4 + TanStack Query in
`frontend/`, five screens (landing, sidebar app shell, conversation view,
chunk detail, in-app documentation), verified against the real API and
covered by 19 component/integration tests. Includes a deliberate scope
decision (no cross-turn context within a conversation), in-app
documentation of the evaluation design, a small additive backend surface
(conversation list/rename/delete), and a known gap (no dark mode / full
responsive layout yet). Full design rationale: [`docs/frontend.md`](frontend.md).

**Correction to Sprint 6/7's design: retrieval confidence moved from
post-evaluation display to a pre-generation preview**, computed live at
the chunk-rail level instead of shown only after generation completes.
Rationale and implementation:
[`docs/anti_hallucination_guardrails.md`](anti_hallucination_guardrails.md).

### Sprint 9 — Integration and bootstrap
- Full dockerization (API, frontend, Qdrant) via Docker Compose
- Bootstrap script/Makefile chaining fetch-data → build-index → run
- **Deliverable**: entire application launchable locally in one command

**Implemented.** Four services in `docker-compose.yml` (`qdrant`, `ollama`,
`api`, `frontend`), a `Makefile` with a `quickstart` target chaining
`fetch-data → build-index → setup-ollama → run`, healthchecks gating
startup order, and three test scripts (`test_frontend_arg.sh`,
`test_container_connectivity.sh`, `smoke_test.py`) guarding the failure
modes specific to this sprint — most notably the browser-vs-internal-URL
split between `VITE_API_BASE` (baked in at frontend build time) and the
API's own internal `QDRANT_URL`/`OLLAMA_API_BASE`. An `hf_cache` volume
avoids re-downloading model weights on every container recreation. Full
design rationale, the exact env-var/build-arg mechanics, and test
coverage: [`docs/dockerization.md`](dockerization.md).

**Ollama: native by default, containerized opt-in — see
[`docs/dockerization.md`](dockerization.md)** (`fix/ollama-native-default`,
superseding this sprint's original "containerize Ollama by default").

### v0 retrospective — checkpoint before Sprint 10

Sprints 0–9 shipped a complete, dockerized, locally-runnable v0 (retrieval
+ reranking + generation + guardrails + persistence + frontend +
one-command bootstrap). A retrospective against real usage of that v0,
before any further implementation branch lands, produced the Sprint
10–14 plan below — Sprint 15 (portfolio polish) remains the final sprint,
after this plan lands rather than immediately following Sprint 9. Two
bugs and one process question drove Sprints 10–11 specifically: the
`/new` "inactive new conversation" bug, the "vérifié status lost on
navigation" bug, and a higher-than-expected real-usage rate of "correct
passage flagged as unsupported" reports against the Sprint 6 guardrail.
Neither `fix/turn-lifecycle-and-manual-generation` nor
`fix/faithfulness-citation-detection` had landed as of this writeup —
both are planned, tracked below under Sprint 10.

### Sprint 10 — Critical fixes (post-v0)

Two independent branches, grouped as one product-level sprint because
both address the trust/reliability surface of the shipped v0.

- **`fix/turn-lifecycle-and-manual-generation`** (planned). Turn creation
  moves from `/generate` to `/retrieve`, fixing the `/new` "inactive new
  conversation" bug and enabling review-before-generation. Automatic
  generation is **removed** — a deliberate reversal of the Sprint 5/6
  default (generation always follows retrieval), driven by direct user
  feedback: researchers want to manually review retrieved chunks before
  committing to a generation call. `should_auto_expand` and the
  collapsed-by-default answer card
  ([`docs/anti_hallucination_guardrails.md`](anti_hallucination_guardrails.md))
  are unchanged — they still govern post-generation display; only the
  generation trigger becomes an explicit button (unified with Sprint 12's
  single "Générer"/"Régénérer" control). Also fixes the "vérifié status
  lost on navigation" bug — root cause likely shared with the
  turn-lifecycle work, to be verified during implementation rather than
  assumed as a second, separate fix.
- **`fix/faithfulness-citation-detection`** (planned). Investigate before
  fixing (standing project discipline) whether "correct passages flagged
  as unsupported" — already known as judge noise from Q008
  ([`docs/anti_hallucination_guardrails.md`](anti_hallucination_guardrails.md))
  — occurs at a higher-than-expected rate in real usage, a genuine gap in
  Layer 1's `check_structure` (prose-embedded fabricated titles, e.g. the
  Q004 case, may be outside Layer 1's original citation-resolution
  scope), or both.

### Sprint 11 — Backend: filtering + chunk mapping

- Chunk retrieval filtering by work and by chronological bounds — a
  Qdrant payload filter on the existing `work_id` field; a static
  work_id → year table derives date-range filtering, so no new indexed
  field or reindex is needed.
- Paragraph-to-chunk_id mapping script, keyed on `paragraph_ids` (stable
  across re-chunking, per the Sprint 1 ingestion design) — resolves the
  gold-dataset-remapping cost that has blocked chunk-size experiments
  since it was first identified (see `docs/gold_dataset_protocol.md`'s
  chunk_id lookup discipline). A plain internal script, not an MCP tool —
  deterministic internal remapping was already ruled out as the wrong
  problem for the MCP layer to solve.

Functional but has no UI in this sprint — the filter UI (work checklist,
date slider) lands in Sprint 12. Between Sprint 11 and Sprint 12, this
capability is real but only exercisable via direct API calls.

### Sprint 12 — UI/UX overhaul

- Landing page reachable only via clicking the app icon after first
  visit — no longer shown once per session automatically (revises
  Sprint 8's behavior).
- Sidebar: three resizable, collapsible sections (user guide + sources
  description; conversation list; settings panel).
- Settings panel exposes `top_k_retrieval`, generation prompt,
  explanation prompt, LLM choice. Defaults remain fixed at whatever
  configuration the gold-dataset evaluation was run against — this panel
  is an optional advanced mode, not a replacement for having one
  evaluated default configuration. Document the exact evaluated default
  values alongside this panel's implementation.
- Chunk rail shows the top 15 post-reranking chunks, top 3 checked by
  default (down from "all included by default"), up to 5 selectable.
- Chunk detail view becomes a chunk-selection expansion view: keeps the
  scrolling rail, adds inspection of a chunk's immediate previous/next
  neighbor in the source work, with the same explain/include actions
  extended to neighbors.
- Chunk card shows the real citation (work, year, page, paragraph)
  instead of the raw `chunk_id`.
- Single "Générer"/"Régénérer" button to the right of the chunk rail —
  the manual-generation trigger from Sprint 10, unified into one
  control.
- Answer display: included chunks listed as bullets; most recent
  generation for a given question shown first; markdown rendering
  enabled for generated text.

### Sprint 13 — MCP layer
Pure search tools: `/retrieve` and `/lookup` (work + paragraph number, or
page number → relevant text), tested with an MCP client. Supersedes the
original Sprint 10 placeholder — scheduled after Sprint 12 per explicit
prioritization; previously this project's lowest-priority item, still
true, now simply next in a defined queue rather than indefinite.

### Sprint 14 — Experimentation
`top_k_retrieval`, RRF `k`, generation prompt, explanation (`judge_chunk`)
prompt, chunk size, LLM choice, LLM temperature. Gated by the same
gold-dataset-volume threshold already established for this class of
decision throughout the project (stems vs. lemmas, cross-encoder vs.
multi-vector — see Sprint 2 and Sprint 4's deferred notes) — unchanged
principle, just a fuller list of candidates now queued behind it.

### Sprint 15 — Portfolio polish
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
│   ├── api/                # FastAPI endpoints — Sprint 7
│   └── mcp_server/         # Sprint 13
├── frontend/               # React (Vite) UI — Sprint 8
├── eval/
│   ├── gold_dataset.csv
│   └── scripts/           # RAGAS, recall@k, etc.
├── docker-compose.yml
├── Makefile                # quickstart target (Sprint 9)
└── pyproject.toml
```
