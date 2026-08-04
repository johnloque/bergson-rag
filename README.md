# Bergson-RAG

Bergson-RAG is a local, French-language chatbot built on the complete works of philosopher Henri Bergson, answering researchers' questions on Bergson's thought with sourced, concise responses.

Features : hybrid retrieval (BM25 + dense + neighborhood search), reranking, and anti-hallucination guardrails with systematic source citation.

## Status

🚧 In development — Sprint 0. See [`docs/ROADMAP.md`](docs/ROADMAP.md)
for architecture details, evaluation methodology, and sprint breakdown.

## Stack

Python · Qdrant (dense + sparse) · BGE-M3 · FastAPI · Docker Compose / Kubernetes · MCP (exposure layer)

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
