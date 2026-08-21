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

**Backend API — implemented (Sprint 7a, `feat/api-endpoints`).** FastAPI
scaffold in `src/api/`, each endpoint a thin wrapper around an existing,
already-tested function, no persistence or session history yet
(`feat/api-persistence`, still pending). Full design rationale, the known
`/evaluate`-trusts-its-input simplification, and test coverage:
[`docs/backend_api.md`](backend_api.md).

**SQLite persistence — implemented (Sprint 7b, `feat/api-persistence`).**
SQLModel over a single local SQLite file (`data/app.db`), storing
conversations, turns, retrieved chunks, generations, evaluations, and
chunk judgments. `/generate` now creates or resumes a turn, and two new
read endpoints — `GET /turns/{id}`, `GET /conversations/{id}` — recover a
turn's full state after a reload. This branch closes two risks flagged as
deferred in prior sprints: Sprint 7a's `/evaluate` trusting a
client-submitted `(query, chunks, answer)` triple, and Sprint 6's lost
badge state for a user who left before evaluation completed. Full schema,
the accepted chunk-text-snapshot limitation, and design rationale:
[`docs/backend_api.md`](backend_api.md).

Sprint 7 (backend API + persistence) is complete.

### Sprint 8 — Frontend
- React (Vite) + Tailwind + TanStack Query, consuming the Sprint 7 API
- Inspect → explain → curate → regenerate loop
- **Deliverable**: working UI against the real API, demoable locally

**Frontend — implemented.** React 19 + Vite + Tailwind v4 + TanStack Query in
`frontend/`. Desktop light mode is the primary deliverable, built exactly to
the design consigne (exact hex tokens, spacing, copy) since no mockup image
files exist for this sprint — the design was approved in a separate
conversation and specified in full in the sprint consigne instead. Five
screens: landing (session-scoped via `sessionStorage`, not `localStorage` —
must reappear on a new tab/session), the sidebar app shell, the conversation
view (query bubble, accumulating processing-steps list, chunk rail with its
pre-generation confidence gauge, collapsed/expanded answer card with
faithfulness highlighting — see the retrieval-confidence-split correction
below), the chunk detail view (`Expliquer`/`Exclure`/`Inclure`), and
an in-app documentation page. State split three ways: TanStack Query for
server reads (`GET /turns/{id}`, `GET /conversations/{id}`), a small React
context (`frontend/src/state/turnUi.tsx`) for the client-owned
included/excluded chunk set and the accumulated `chunk_judgments` dict (both
explicitly client-side until a `/generate` or `/judge-chunk` call sends
them, per this sprint's spec), and a module-level chunk-text cache
(`frontend/src/state/chunkCache.ts`) working around the backend's own
accepted chunk-text-snapshot limitation (`docs/backend_api.md`) — a turn
whose chunks were never fetched client-side this session (e.g. a cold
reload of an old conversation) falls back to a placeholder rather than
fabricating content. Verified against the real API (Qdrant + local Ollama
judge/generation models running) as well as 19 component/integration tests
(Vitest + Testing Library, mocked fetch) covering every behavior called out
in the sprint's Tests section — see `frontend/src/**/*.test.tsx`.

Small, additive backend surface added alongside this sprint (not part of
Sprint 7): `GET /conversations` (list, newest first), `PATCH
/conversations/{id}` (rename), `DELETE /conversations/{id}` (cascading
delete) — Sprint 7 only shipped lookup-by-id, but the sidebar's
conversation list and the landing page's "last conversation" redirect have
no way to enumerate conversations without it. `Conversation` gained a
nullable `title` column for the rename action.

**Known gap, not a finished feature: dark mode and full responsive layout.**
The design tokens are CSS custom properties (`frontend/src/index.css`), not
hardcoded Tailwind colors, specifically so a dark-mode pass is a values-swap
later rather than a rewrite — but no dark-mode values are defined yet, since
that design pass hasn't happened. Likewise, only the sidebar/chunk-rail
breakpoints that were straightforward with Tailwind's responsive utilities
are in place; the layout has not been comprehensively designed or tested
for mobile/tablet widths. Both remain explicitly open, to be picked up in a
later, dedicated design pass rather than assumed complete from this sprint.

**Correction to Sprint 6/7a-b/8's original design: retrieval confidence
moved from post-evaluation display to a pre-generation preview.**
Originally, the retrieval confidence tier was computed inside
`generate_evaluation` (Sprint 6) and surfaced as a field on `/evaluate`'s
response (Sprint 7a-b), rendered as a gauge inside the expanded,
post-evaluation answer card (Sprint 8). On reflection this showed the
signal at the wrong moment and in the wrong place: retrieval confidence is
a property of the *evidence*, knowable before generation ever runs, not a
property of the *answer* — showing it only after `/evaluate` completed
meant the user had already committed to generating (and had to wait through
the full generate → evaluate round trip) before seeing a signal that could
have informed whether to curate the chunk rail first. It also duplicated
`should_auto_expand`'s own internal use of the same tier without adding
information, since a low tier already suppresses auto-expand.

Fixed by extracting the tier computation into `src.generation.signals.
retrieval_confidence_tier` (already a standalone function; `generate_evaluation`
now takes the tier as a parameter instead of computing it) and giving it two
call sites, not the previous single implicit one: a new `POST
/confidence-preview` endpoint, called live by the frontend at the chunk-rail
level on every include/exclude toggle (debounced ~300ms), and `POST
/generate`, which computes the same tier server-side over the chunks it was
actually given and persists it on the `generations` row — never a
client-submitted value, the same trust boundary Sprint 7b already applied to
`/evaluate`'s `(query, chunks, answer)`. `/evaluate` reads that persisted
value back purely to gate `should_auto_expand` internally; its response no
longer carries a `retrieval_confidence_tier` field, since re-showing it
there would just duplicate what `/confidence-preview` already showed before
generation. `should_auto_expand`'s decision logic itself is unchanged (tier
at "moyenne" or above AND no unsupported claims) — only where its confidence
input comes from changed. On the frontend, the confidence gauge
(`ConfidenceGauge.tsx`, unchanged visually — same 4-segment bar, `--blue`
for the confident tiers, `--gray-dark` for the two weak tiers) moved from
the expanded answer card to directly above the chunk rail (`ChunkRail.tsx`);
the answer card now renders only the citation integrity flag and
faithfulness highlighting.

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
│   ├── api/                # FastAPI endpoints — Sprint 7
│   └── mcp_server/         # Sprint 10
├── frontend/               # React (Vite) UI — Sprint 8
├── eval/
│   ├── gold_dataset.csv
│   └── scripts/           # RAGAS, recall@k, etc.
├── docker-compose.yml
├── Makefile                # quickstart target (Sprint 9)
└── pyproject.toml
```
