# Bergson-RAG

Bergson-RAG is a local, French-language chatbot built on the complete
works of philosopher Henri Bergson. Its purpose is to help users
understand Bergson's thought on any specific notion he addressed, with
answers grounded in and cited from the source texts.

## What it does

The user asks a question in French. The system retrieves relevant
passages from Bergson's works, and automatically generates a
synthesized, cited and explainable answer.

### Interaction flow

1. **Ask** — the user submits a question.
2. **Answer** — the system retrieves, reranks, and generates a cited
   synthesis automatically.
3. **Inspect** — the chunks used to produce the answer are shown
   alongside it, not hidden behind the synthesis.
4. **Explain (on demand)** — for any chunk, the user can request a
   short, LLM-generated justification of why (or why not) it actually
   answers the question — computed only on click, not by default.
5. **Curate** — the user can deselect any chunk they judge irrelevant.
6. **Regenerate** — the answer is regenerated from the curated chunk
   selection only.

This flow keeps source discovery and interpretation as two distinct,
user-visible steps rather than one opaque pass — the user is never
forced through a manual curation step to get a first answer, but always
has the option to refine one, so the generation pipeline does not remain a black box. See `docs/ROADMAP.md` for the technical
decisions behind each step.

## Status

🚧 In development — Sprint 0 (scoping). See [`docs/ROADMAP.md`](docs/ROADMAP.md) for architecture details, evaluation methodology, and sprint breakdown.

## Stack

**Retrieval & indexing**
- Qdrant — dense + sparse vector store, hybrid search backend
- BGE-M3 — multilingual dense embeddings
- BM25 (on lemmas) — sparse/lexical matching
- FastText *(candidate, `exp/` branch)* — query expansion, vocabulary-drift mitigation

**Reranking & generation**
- bge-reranker-v2-m3 — default, always-on cross-encoder relevance score
- LLM (local via Ollama, API fallback) — answer generation, and on-demand
  per-chunk relevance judgments (`judge_chunks`)

**Backend & API**
- FastAPI — three-endpoint API (`retrieve` / `generate_from_chunks` /
  `judge_chunks`)
- SQLite — conversation history: questions, answers, curated chunk
  selections, requested relevance judgments

**Frontend**
- React (Vite) — inspect → explain → curate → regenerate flow
- Tailwind CSS — styling
- TanStack Query — independent async state per chunk (on-demand
  judgments), API response caching

**Deployment**
- Docker Compose — reference local setup
- Kubernetes — optional, documented deployment path

**Exposure layer**
- MCP — pure search tool, no generation, usable from any MCP client

## Repo structure

See [`docs/ROADMAP.md`](docs/ROADMAP.md#target-repo-structure).

## License

MIT — see [`LICENSE`](LICENSE). The source corpus (the works of Henri
Bergson, who died in January 1941) has been in the public domain in
France since January 1, 2012, under the standard 70-years-post-mortem
rule. This is not legal advice; independent verification is recommended before any commercial use.

## Contributing

This repo follows a PR workflow even in solo development, as a
demonstration of engineering practice. See [`CONTRIBUTING.md`](CONTRIBUTING.md).
