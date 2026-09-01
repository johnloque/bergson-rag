# Bergson-RAG

Bergson-RAG is a local, French-language chatbot built on the complete
works of philosopher Henri Bergson. Its purpose is to help users
understand Bergson's thought on any specific notion he addressed, with
answers grounded in and cited from the source texts.

## What it does

The user asks a question in French, optionally narrowed by work and/or
publication date. The system retrieves and reranks relevant passages,
lets the user inspect and curate them (explaining any chunk's relevance
on demand), and only then generates a synthesized, cited answer on
request — reviewing evidence and generating are two distinct,
user-triggered steps, not one automatic pass. See the in-app "Guide
d'utilisation" for the full step-by-step flow, and
[`docs/ROADMAP.md`](docs/ROADMAP.md) for the technical decisions behind
each step.

## Known limitations & scope

This system is designed and evaluated for questions answerable from a
small, boundable set of passages (factual and definitional questions).
It deliberately does not attempt:

- **Transversal/distributional questions** — e.g. tracing a recurring
  image or a concept whose meaning shifts across the corpus. Verified
  empirically (see `docs/ROADMAP.md`) rather than assumed: doctrinal
  questions tend to be anchored in one canonical text; recurring-image
  and evolving-term questions tend to be genuinely dispersed and are out
  of reach for top-k retrieval + single-pass LLM synthesis, regardless
  of prompt quality.
- **Comparative and open-interpretive questions** (comparing concepts
  across works, contested philosophical positions) — deferred to a
  separate, complementary project using a different architecture
  (graph-based propagation over the corpus).
- **Exhaustive lexical/concordance analysis** — a mature, specialized
  tool (TXM) already exists for this and is not being rebuilt here.

## Status

🚧 In development — Sprint 12 (UI/UX overhaul) in progress: retrieval
filters, chunk-rail defaults, citations, and answer-display improvements
have landed; the sidebar redesign and settings panel are still pending.
See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full sprint breakdown
and architecture decisions.

## Running it

Requires Docker, `uv`, and `git`. `make quickstart` fetches the corpus,
builds the index, sets up native Ollama and the native ML service, and
starts the stack (frontend at `http://localhost:3000`, API at
`http://localhost:8000`). See [`docs/dockerization.md`](docs/dockerization.md)
for the exact command sequence, dependency order, and native-vs-containerized
tradeoffs.

## Stack

**Retrieval & indexing**
- Qdrant — dense + sparse vector store, hybrid search backend
- BGE-M3 — multilingual dense embeddings
- BM25 (on French Snowball stems) — sparse/lexical matching

**Reranking & generation**
- bge-reranker-v2-m3 — default, always-on cross-encoder relevance score
- LLM (local via Ollama, API fallback) — answer generation, single-query
  reformulation, and on-demand per-chunk relevance judgments
  (`judge_chunks`)

**Backend & API**
- FastAPI — endpoints for retrieval, generation, evaluation, and
  per-chunk judgments
- SQLite — conversation history (questions, answers, curated chunk
  selections, requested relevance judgments)
- `ml_service` — standalone native FastAPI process serving the dense
  embedder, sparse embedder, and cross-encoder reranker; `api` calls it
  over HTTP when configured, otherwise loads the same models in-process

**Frontend**
- React (Vite) — retrieve → inspect → explain → curate → generate →
  evaluate flow
- Tailwind CSS — styling
- TanStack Query — independent async state per chunk (on-demand
  judgments), API response caching

**Deployment**
- Docker Compose — reference local setup
- Kubernetes — not implemented; would be the natural path to scale in
  production, out of scope for this demo

**Exposure layer**
- MCP — pure search tool, no generation; lowest priority, first to drop
  if time is short

## Repo structure

See [`docs/ROADMAP.md`](docs/ROADMAP.md#target-repo-structure).

## License

MIT — see [`LICENSE`](LICENSE). The source corpus (the works of Henri
Bergson, who died in January 1941) has been in the public domain in
France since January 1, 2012, under the standard 70-years-post-mortem
rule. This is not legal advice;
independent verification is recommended before any commercial use.

## Contributing

This repo follows a PR workflow even in solo development, as a
demonstration of engineering practice. See [`CONTRIBUTING.md`](CONTRIBUTING.md).
