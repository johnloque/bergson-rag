.PHONY: fetch-data build-index pull-model run quickstart test-connectivity test-frontend-arg smoke-test

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

# The ollama container always starts empty -- the model is never baked
# into the image (docs/ROADMAP.md) -- so it must be pulled explicitly.
# Requires the ollama container already running (`make run`, or
# `quickstart` below, which calls this after `run`).
pull-model:
	docker compose exec ollama ollama pull mistral

# Brings up all four services (qdrant, ollama, api, frontend), building
# any image that's missing or stale. api won't actually start serving
# until qdrant and ollama report healthy (docker-compose.yml's
# `depends_on: condition: service_healthy`), and frontend won't start
# until api is healthy in turn -- no manual wait needed here.
run:
	docker compose up -d --build

# Dependency order actually implemented: fetch-data -> build-index -> run
# -> pull-model.
#   - build-index must follow fetch-data: it ingests data/raw/corpus,
#     which doesn't exist until fetch-data runs.
#   - build-index must precede a *useful* run: an api container against an
#     empty Qdrant collection starts and reports healthy fine, it just has
#     nothing to retrieve.
#   - pull-model only needs the ollama container started, which `run`
#     already guarantees. It's last here, but nothing breaks if it runs
#     any time after `run` and before a real /generate call -- the api
#     container itself starts and passes its healthcheck (GET /docs, no
#     LLM call involved) whether or not a model has been pulled yet.
quickstart: fetch-data build-index run pull-model
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
