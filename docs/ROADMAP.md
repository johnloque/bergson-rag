# Chatbot RAG — Complete works of Henri Bergson

## Validated architecture decisions

- **Source data**: two aligned XML granularities, both kept — paragraph
  level as the canonical text source (display, chunking, embedding,
  citation), word+lemma+POS level as the lexical index source (BM25 on
  lemmas, lemma-based lookup), joined by paragraph id.
- **Chunking**: hierarchical (parent/child), leveraging the existing XML
  structure rather than a generic splitter.
- **Retrieval**: hybrid BM25 (on lemmas) + dense (BGE-M3) + neighborhood
  search in the source text, fused via RRF. FastText embeddings trained
  on the corpus are a candidate addition for query expansion and
  vocabulary verification, to be validated as an `exp/` branch against
  the vocabulary-drift subset of the gold dataset before adoption.
- **Query reformulation**: multi-query / decomposition before retrieval,
  to absorb the gap between contemporary vocabulary and Bergson's own
  vocabulary (*vocabulary drift*).
- **Scoring**: cross-encoder reranker (bge-reranker-v2-m3) as the
  default, always-on relevance score. A separate, more expensive
  LLM-as-judge relevance judgment (a short textual justification per
  chunk) is available on demand only, not computed by default — reserved
  for the UI's "explain" action. Reasoned about by rank rather than
  absolute calibration when aggregated over the gold dataset; not needed
  for the single-query, on-demand UI case, where the justification is
  shown as-is.
- **Generation**: the prompt is conditioned on observable properties of
  the retrieved, reranked evidence (does it span one work or several,
  does it converge or diverge) rather than on a question category label
  — no such label exists in production. Question categories
  (factual/definitional/comparative/contested) exist only in the gold
  dataset, as a held-out field for stratified evaluation, the same way
  the work/paragraph ground truth is held out from the system's input.
- **Anti-hallucination guardrails**: post-generation validation layer +
  mandatory citations; generated syntheses are treated as interpretive
  proposals to verify, not as definitive answers.
- **API decomposition** (Sprint 6): three independent endpoints rather
  than one monolithic call —
  - `retrieve(query)` — hybrid search + reranking, returns chunks
  - `generate_from_chunks(query, chunks)` — synthesis from a given,
    possibly user-curated, chunk selection
  - `judge_chunks(query, chunks)` — on-demand relevance judgment
    (score + justification) per chunk, called only when the user
    requests it
- **Infra**: Qdrant (dense + sparse), FastAPI, Docker Compose as the
  reference setup, Kubernetes manifests as a documented option (no real
  scaling need at this stage).
- **MCP**: exposure layer (Sprint 9), deliberately a pure search tool —
  returns chunks and metadata, no generation — mirroring the same
  discovery/interpretation separation as the chatbot's own inspect step.
  Two tools planned: hybrid search, exact-reference lookup (XPath
  navigation + lemma search).

## Evaluation methodology

The system does not aim to settle hermeneutic debates but to retrieve
and faithfully restitute what the corpus says. The gold dataset is
stratified by question type, with two distinct evaluation regimes:

- **Factual / definitional / comparative** (outcome-based): ground truth
  = one or more `(work, paragraph_id)` pairs. Metrics: recall@k, MRR,
  faithfulness, context precision/recall (RAGAS). Comparative items may
  additionally be scored on a process-based criterion (does the answer
  stay anchored to the cited passages rather than asserting an
  unsupported linear evolution).
- **Contested / interpretive** (process-based): no content ground truth.
  Evaluates the system's behavior (does it cite several contrasting
  passages, does it flag the absence of consensus), not the correctness
  of an interpretation.

Full annotation protocol: `docs/gold_dataset_protocol.md`.

## Sprint breakdown

Each sprint targets 1–2 weeks of part-time work and ends with a
demonstrable deliverable. From Sprint 3 onward, each sprint closes with
a measured metric, not just "it works".

### Sprint 0 — Scoping and foundations
Data schema audit, copyright confirmation, gold dataset construction,
dev environment setup.

### Sprint 1 — Ingestion and chunking
Parse XML into structured objects, hierarchical chunking aligned across
the two source granularities, unit tests on chunk boundaries.

### Sprint 2 — Hybrid indexing
Qdrant setup, dense + sparse collections, embedding generation, BM25
indexing from lemmas.

### Sprint 3 — Hybrid retrieval + query reformulation
RRF fusion, neighborhood search, multi-query reformulation. `exp/`
branch evaluating FastText query expansion against the vocabulary-drift
subset of the gold dataset. First retrieval-only evaluation (recall@k,
MRR).

### Sprint 4 — Reranking and generation
Cross-encoder integration, evidence-conditioned prompt design (not
category-conditioned), LLM integration (local + API fallback),
preliminary end-to-end evaluation (RAGAS).

### Sprint 5 — Anti-hallucination guardrails
Post-generation validation, explicit "no reliable answer" handling,
citation formatting, before/after metrics on the gold dataset.

### Sprint 6 — Backend API and persistence
- Three-endpoint FastAPI (`retrieve` / `generate_from_chunks` /
  `judge_chunks`)
- SQLite schema and persistence: questions, answers, curated chunk
  selections, requested relevance judgments
- API-level tests (no UI yet — exercised via pytest / curl / Postman)
- **Deliverable**: fully functional, tested API, usable independently of
  any frontend

### Sprint 7 — Frontend
- React (Vite) + Tailwind + TanStack Query, consuming the Sprint 6 API
- Inspect → explain → curate → regenerate loop, with independent
  per-chunk async state for on-demand relevance judgments
- **Deliverable**: working UI against the real API, demoable locally
  (frontend + API running side by side, not yet containerized together)

### Sprint 8 — Integration and bootstrap
- Full dockerization (API, frontend, Qdrant) via Docker Compose
- Bootstrap script/Makefile chaining fetch-data → build-index → run
- **Deliverable**: entire application launchable locally in one command

### Sprint 9 — MCP layer
Pure search tools (hybrid search, exact-reference lookup), tested with
an MCP client.

### Sprint 10 — Kubernetes (optional extension)
Manifests, local testing on kind/minikube, documented Compose vs. K8s
rationale.

### Sprint 11 — Portfolio polish
Complete README, evaluation results presented clearly, technical blog
post, accessible demo.

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
├── k8s/                   # optional manifests (Sprint 10)
├── docker-compose.yml
├── Makefile                # quickstart target (Sprint 8)
└── pyproject.toml
```
