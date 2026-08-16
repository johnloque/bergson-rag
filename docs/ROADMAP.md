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
evaluation (recall@k, MRR).

### Sprint 4 — Reranking and generation
Cross-encoder integration, single-mode prompt design, LLM integration
(local + API fallback), preliminary end-to-end evaluation (RAGAS).

### Sprint 5 — Anti-hallucination guardrails
Post-generation validation, explicit "no reliable answer" handling,
citation formatting, before/after metrics on the gold dataset.

### Sprint 6 — Backend API and persistence
- Three-endpoint FastAPI (`retrieve` / `generate_from_chunks` /
  `judge_chunks`)
- API-level tests (no UI yet)
- SQLite persistence as fast-follow, not a blocker for this sprint's
  deliverable
- **Deliverable**: fully functional, tested API, usable independently of
  any frontend

### Sprint 7 — Frontend
- React (Vite) + Tailwind + TanStack Query, consuming the Sprint 6 API
- Inspect → explain → curate → regenerate loop
- **Deliverable**: working UI against the real API, demoable locally

### Sprint 8 — Integration and bootstrap
- Full dockerization (API, frontend, Qdrant) via Docker Compose
- Bootstrap script/Makefile chaining fetch-data → build-index → run
- **Deliverable**: entire application launchable locally in one command

### Sprint 9 — MCP layer
Pure search tools (hybrid search, exact-reference lookup), tested with
an MCP client. First to drop if time is constrained.

### Sprint 10 — Portfolio polish
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
│   └── mcp_server/         # Sprint 9
├── frontend/               # React (Vite) UI — Sprint 7
├── eval/
│   ├── gold_dataset.csv
│   └── scripts/           # RAGAS, recall@k, etc.
├── docker-compose.yml
├── Makefile                # quickstart target (Sprint 8)
└── pyproject.toml
```
