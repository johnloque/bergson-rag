# Chatbot RAG — Complete works of Henri Bergson

Data scientist / ML engineer NLP portfolio project. Local RAG chatbot
answering researchers' questions on Bergson's thought with sourced,
concise responses, built from an XML corpus of the 8 major works
(paragraph and word+lemma+POS granularity).

## Status

Sprint 0 — scoping and foundations. No application code yet.

## Validated architecture decisions

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

Inspired by HistoRAG (Kim-Baumann & Hiltmann, 2026) — a RAG architecture
designed for history, adapted here to philosophy. Documented differences:
LLM-judge rubric criteria to be defined specifically for Bergson (no
published standard for philosophy to date); no temporal windowing (the
corpus is not a diachronic press corpus but the corpus of a single
author — the relevant analogue would rather be windowing by work/period
of Bergson's thought, to be evaluated).

## Sprint 0 checklist

- [ ] Audit the XML schema (see `docs/xml_audit_checklist.md`)
- [ ] Confirm copyright status (Bergson, died 1941 — public domain in
      France since 2011; to be confirmed for any critical editions under
      separate rights)
- [ ] Build gold dataset v0 (`gold_dataset_template.csv`) — 50 to 100
      annotated, stratified questions, **before** any retrieval code
- [ ] Set up environment (poetry/uv), pre-commit, Docker Compose skeleton
- [ ] Technical README detailing the repo structure

## Target repo structure

```
bergson-rag/
├── data/
│   ├── raw/              # source XML (not versioned if large)
│   └── processed/        # chunks, index
├── docs/                 # audits, methodology notes
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
└── pyproject.toml
```
