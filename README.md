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
user-visible steps rather than one opaque pass. See `docs/ROADMAP.md`
for the technical decisions behind each step.

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

🚧 In development — Sprint 9 (Integration and bootstrap) complete: the
whole stack (Qdrant, Ollama, API, frontend) runs via Docker Compose, with
Ollama itself defaulting to a fast, native (non-Docker) install rather
than a container (`fix/ollama-native-default`, see below).
See [`docs/ROADMAP.md`](docs/ROADMAP.md) for architecture details,
evaluation methodology, and sprint breakdown.

## Quickstart

Requires Docker, `uv`, and `git`. On macOS, also requires (or installs via
Homebrew) native Ollama; on Linux, the official Ollama install script.

```sh
make quickstart   # fetch corpus -> build index -> setup native Ollama -> start qdrant/api/frontend
```

This chains `fetch-data` (clones the source XML), `build-index` (runs
ingestion + indexing against a `qdrant` container, on the host via `uv
run`), `setup-ollama` (`scripts/setup_ollama.sh` — installs/starts Ollama
directly on the host, not in Docker, and pulls `mistral` into it), and
`run` (`docker compose up -d --build` — `qdrant`, `api`, `frontend`; the
containerized `ollama` service does *not* start by default). Once it
finishes: frontend at `http://localhost:3000`, API at
`http://localhost:8000`, talking to native host Ollama
(Metal-accelerated on Apple Silicon). See `docs/dockerization.md` for the
exact dependency order and what each Makefile target does, and
`Makefile`/`docker-compose.yml` directly for the underlying commands.

### Why native Ollama is the default (`fix/ollama-native-default`)

Docker Desktop on Apple Silicon has no Metal (GPU) passthrough into its
Linux VM — a containerized Ollama is always CPU-only there, regardless of
Compose config, and was measured ~3-5x slower than native host Ollama for
the same generation call. `make quickstart` / `make run` reflect that:
native Ollama (`make setup-ollama`) is the default, and the containerized
`ollama` service is gated behind a Compose profile so it never starts
unless asked for explicitly:

```sh
make run-with-ollama   # opt-in fallback: containerized Ollama, CPU-only, slower
```

Useful when a usable host Ollama install isn't an option (CI, a
locked-down Linux box, a quick one-off clone) — see `docs/dockerization.md`
for the full mechanism (the `with-ollama` Compose profile, and how
`OLLAMA_API_BASE` switches between `host.docker.internal` and the
internal `ollama` service name).

### Faster local dev (everything native, not just Ollama)

The Docker stack (`qdrant`/`api`/`frontend` containerized, Ollama native)
is for reproducibility ("clone and run one command"), not necessarily the
fastest loop for active backend/frontend iteration. For that, run
everything except Qdrant directly on the host instead:

```sh
docker compose up -d qdrant        # keep Qdrant containerized
make setup-ollama                  # or: ollama serve & ; ollama pull mistral
uv run uvicorn src.api.main:app --reload --port 8000
cd frontend && npm run dev         # http://localhost:5173
```

No env var overrides needed — `QDRANT_URL`/`OLLAMA_API_BASE` default to
`localhost` (`src/api/dependencies.py`, litellm's own default), the
frontend's dev-mode `VITE_API_BASE` fallback is already
`http://localhost:8000` (`frontend/src/api/client.ts`), and the API's CORS
allowlist already includes the Vite dev server origin unconditionally
(`FRONTEND_DEV_ORIGIN`, `src/api/main.py`) regardless of `CORS_ORIGINS`.
This is exactly the pre-Sprint-9 dev flow; Sprint 9 only added the
containerized path on top of it, it didn't replace it.

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
- FastAPI — three-endpoint API (`retrieve` / `generate_from_chunks` /
  `judge_chunks`)
- SQLite — conversation history (questions, answers, curated chunk
  selections, requested relevance judgments); fast-follow, not required
  for the first working version

**Frontend**
- React (Vite) — inspect → explain → curate → regenerate flow
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
