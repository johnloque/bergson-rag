# bergson-rag

Bergson-RAG is a local, French-language chatbot built on the complete
works of philosopher Henri Bergson. Its purpose is to help users
understand Bergson's thought on any specific notion he addressed.

Hybrid retrieval (BM25 + dense + neighborhood search), reranking, and
anti-hallucination guardrails with systematic source citation.

Data scientist / ML engineer NLP portfolio project.

## Status

🚧 In development — Sprint 0 (scoping). See [`docs/ROADMAP.md`](docs/ROADMAP.md)
for architecture details, evaluation methodology, and sprint breakdown.

## Stack

Python · Qdrant (dense + sparse) · BGE-M3 · FastAPI · Docker Compose ·
Kubernetes (optional deployment, documented) · MCP (exposure layer)

## Repo structure

See [`docs/ROADMAP.md`](docs/ROADMAP.md#target-repo-structure).

## License

MIT — see [`LICENSE`](LICENSE). The source corpus (the works of Henri
Bergson, who died in 1941) is in the public domain in France.

## Contributing

This repo follows a PR workflow even in solo development, as a
demonstration of engineering practice. See [`CONTRIBUTING.md`](CONTRIBUTING.md).
