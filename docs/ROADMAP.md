# Chatbot RAG — Complete works of Henri Bergson

## Validated architecture decisions

- **Source data**: two aligned XML granularities, both kept — paragraph
  level as the canonical text source (display, chunking, embedding,
  citation), word+lemma+POS level as the lexical index source (BM25 on
  lemmas, lemma-based lookup), joined by paragraph id.
- **Chunking**: hierarchical (parent/child), leveraging the existing XML
  structure rather than a generic splitter.
- **Retrieval**: hybrid BM25 (on lemmas) + dense (BGE-M3) + neighborhood
  search in the source text, fused via RRF.
- **Query reformulation**: multi-query / decomposition before retrieval,
  to absorb the gap between contemporary vocabulary and Bergson's own
  vocabulary (*vocabulary drift*, cf. HistoRAG, Kim-Baumann & Hiltmann
  2026).
- **Reranking**: multilingual cross-encoder (bge-reranker-v2-m3).
- **Anti-hallucination guardrails**: post-generation validation layer +
  mandatory citations; generated syntheses are treated as interpretive
  proposals to verify (the *Zwischentexte* concept), not as definitive
  answers.
- **Infra**: Qdrant (dense + sparse), FastAPI, Docker Compose as the
  reference setup, Kubernetes manifests as a documented option (no real
  scaling need at this stage).
- **MCP**: exposure layer at the end of the project (Sprint 7), not core
  to the pipeline. Two tools planned: hybrid search, exact-reference
  lookup (XPath navigation + lemma search).

## Evaluation methodology

The system does not aim to settle hermeneutic debates but to retrieve and
faithfully restitute what the corpus says. The test set is therefore
stratified by question type (see `gold_dataset_template.csv`), with two
distinct evaluation regimes:

- **Factual / definitional / comparative** (outcome-based): ground truth
  = set of reference passages (paragraph_id). Metrics: recall@k, MRR,
  faithfulness, context precision/recall (RAGAS).
- **Contested / interpretive** (process-based): no content ground truth.
  We evaluate the system's *behavior* (does it cite several contrasting
  passages? does it flag the absence of consensus?), not the correctness
  of an interpretation.

Inspired by HistoRAG ([Kim-Baumann & Hiltmann, 2026](https://arxiv.org/abs/2606.18103)) — a RAG architecture
designed for history, adapted here to philosophy. Documented differences:
LLM-judge rubric criteria to be defined specifically for Bergson (no
published standard for philosophy to date); no temporal windowing (the
corpus is not a diachronic press corpus but the corpus of a single
author — the relevant analogue would rather be windowing by work/period
of Bergson's thought, to be evaluated).

## Sprint breakdown

Each sprint targets 1–2 weeks of part-time work and ends with a
demonstrable deliverable. From Sprint 3 onward, each sprint closes with a
measured metric (not just "it works") — the point being to demonstrate
*how* each improvement was validated, not just that it happened.

### Sprint 0 — Scoping and foundations

- Finalize the data schema from the XML: which tags, which granularity
  per use case (paragraph for retrieval, word/lemma/POS for lexical
  indexing)
- Confirm and document the corpus's copyright status
- Build the evaluation gold dataset (50–100 annotated questions with
  expected sources) — **before** any retrieval code is written, not after
- Repo setup: project structure, environment, pre-commit, Docker Compose
  skeleton, initial README
- **Deliverable**: structured repo, corpus inventoried, gold dataset v0,
  reproducible environment

### Sprint 1 — Ingestion and chunking

- Parse XML into structured Python objects (metadata: work, chapter,
  section, position)
- Implement hierarchical chunking (parent/child), aligning the paragraph
  and word-level sources by paragraph id
- Unit tests on chunking (no mid-argument cuts, consistent sizes)
- **Deliverable**: tested ingestion pipeline, chunks stored (JSON/Parquet)
  ready for indexing

### Sprint 2 — Hybrid indexing

- Qdrant setup locally (Docker), dense + sparse collections
- Embedding generation (BGE-M3), BM25/sparse indexing from lemmas
- Idempotent indexing script (safely rerunnable if the corpus changes)
- **Deliverable**: populated vector store, working raw queries (no
  reformulation, no reranking yet)

### Sprint 3 — Hybrid retrieval + query reformulation

- BM25/dense fusion (RRF or weighting)
- Neighborhood search in source texts (retrieving the parent context
  around a matched chunk)
- Query reformulation/expansion module (multi-query, possibly HyDE)
- Retrieval-only evaluation on the gold dataset (recall@k, MRR) — first
  objective quality measurement
- **Deliverable**: evaluated, versioned retrieval engine

### Sprint 4 — Reranking and generation

- Cross-encoder reranker integration
- Prompt engineering for generation (synthesis + source citation)
- LLM integration (local via Ollama, with an API fallback)
- Preliminary end-to-end evaluation (RAGAS: faithfulness, answer
  relevancy)
- **Deliverable**: functional end-to-end RAG pipeline (CLI/notebook)

### Sprint 5 — Anti-hallucination guardrails

- Post-generation validation layer (verify every claim ties back to an
  actually retrieved source passage)
- Explicit handling of "no reliable answer in the corpus" instead of
  forcing a response
- Systematic citation formatting (work, section/page)
- Iterate on the gold dataset with guardrails active, measure the
  improvement
- **Deliverable**: hardened pipeline, before/after metrics on the test
  set

### Sprint 6 — API and interface

- FastAPI exposing the pipeline (retrieval, generation, health check
  endpoints)
- Streamlit/Gradio frontend displaying sources
- Full dockerization, working end-to-end Docker Compose
- Bootstrap script (`Makefile` with a `quickstart` target chaining
  fetch-data → build-index → run) so the whole application can be
  launched locally in one command — written only now, once every
  component it chains together actually exists
- **Deliverable**: usable end-to-end application, demoable locally

### Sprint 7 — MCP layer

- Expose key capabilities (hybrid search, exact-reference lookup) as MCP
  tools
- Test with an MCP client (Claude Desktop)
- **Deliverable**: functional, documented MCP server

### Sprint 8 — Kubernetes (optional extension)

- Kubernetes manifests (Deployment, Service, StatefulSet+PVC for Qdrant,
  ConfigMap/Secrets)
- Local testing on kind/minikube
- Architecture note justifying Compose vs. Kubernetes
- **Deliverable**: working manifests + documented rationale

### Sprint 9 — Portfolio polish

- Complete README with architecture, justified technical choices, known
  limitations
- Evaluation results presented clearly (before/after tables/charts per
  improvement)
- Possibly a technical blog post detailing the challenges encountered
  (Bergsonian terminology, argumentative chunking, etc.)
- Demo deployed somewhere accessible (even in a limited form)
- **Deliverable**: interview-ready project with a clear narrative of the
  decisions made

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
│   └── mcp_server/         # Sprint 7
├── eval/
│   ├── gold_dataset.csv
│   └── scripts/           # RAGAS, recall@k, etc.
├── k8s/                   # optional manifests (Sprint 8)
├── docker-compose.yml
├── Makefile                # quickstart target (Sprint 6)
└── pyproject.toml
```