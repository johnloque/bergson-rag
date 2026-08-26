.PHONY: fetch-data build-index setup-ollama run run-with-ollama quickstart test-connectivity test-frontend-arg smoke-test

# Fetches the paragraph-level XML corpus (scripts/fetch_corpus.sh). First
# step, no other dependency.
fetch-data:
	./scripts/fetch_corpus.sh

# Sprint 1 ingestion + Sprint 2 indexing, run on the HOST via uv (not
# inside a container: these scripts need the dev venv's spaCy model, and
# talk to Qdrant over its published host port, not the internal Docker
# network). Starts qdrant if it isn't already running; does not touch
# ollama/api/frontend.
build-index:
	docker compose up -d qdrant
	uv run python scripts/run_ingestion.py
	uv run python scripts/build_index.py

# Native Ollama setup (docs/dockerization.md) -- the fast, default path:
# installs/starts Ollama directly on the host (Metal-accelerated on
# Apple Silicon) and pulls mistral into it. NOT Docker-based. See
# scripts/setup_ollama.sh.
setup-ollama:
	./scripts/setup_ollama.sh

# Brings up qdrant, api, and frontend only, building any image that's
# missing or stale -- the `ollama` service is gated behind the
# `with-ollama` Compose profile (docker-compose.yml) and does NOT start
# here. api talks to native host Ollama via OLLAMA_API_BASE, which
# defaults to http://host.docker.internal:11434 (see `make setup-ollama`,
# above). api won't actually start serving until qdrant reports healthy,
# and frontend won't start until api is healthy in turn -- no manual wait
# needed here.
run:
	docker compose up -d --build

# Opt-in, CPU-only fallback path (docs/dockerization.md): starts the
# containerized `ollama` service too (Docker Desktop can't pass Metal
# through to it, so it's measured 3-5x slower than native) and pulls
# mistral into that container specifically -- it always starts empty, the
# model is never baked into the image. Overrides OLLAMA_API_BASE to the
# internal service name (http://ollama:11434) so api actually talks to
# THIS container -- without the override it would still point at
# host.docker.internal (the `run` default) even with the container up.
run-with-ollama:
	OLLAMA_API_BASE=http://ollama:11434 docker compose --profile with-ollama up -d --build
	docker compose exec ollama ollama pull mistral

# Dependency order actually implemented: fetch-data -> build-index ->
# setup-ollama -> run.
#   - build-index must follow fetch-data: it ingests data/raw/corpus,
#     which doesn't exist until fetch-data runs.
#   - build-index must precede a *useful* run: an api container against an
#     empty Qdrant collection starts and reports healthy fine, it just has
#     nothing to retrieve.
#   - setup-ollama only needs to finish before a real /generate call --
#     api's own healthcheck (GET /docs, no LLM call involved) starts and
#     reports healthy either way -- but it's ordered before `run` here so
#     `make quickstart` leaves a fully working stack with no follow-up
#     step required.
quickstart: fetch-data build-index setup-ollama run
	@echo ""
	@echo "Stack is up: frontend http://localhost:3000, api http://localhost:8000"
	@echo "Run 'make smoke-test' to verify the full retrieve -> generate chain."

# Sprint 9 test targets (docs/ROADMAP.md), run against an already-running
# stack (`make run` or `make quickstart`).
test-connectivity:
	./scripts/test_container_connectivity.sh

test-frontend-arg:
	./scripts/test_frontend_arg.sh

smoke-test:
	uv run python scripts/smoke_test.py
