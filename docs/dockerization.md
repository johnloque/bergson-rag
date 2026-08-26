# Dockerization and bootstrap (Sprint 9)

Four services in `docker-compose.yml` (`qdrant`, `ollama`, `api`,
`frontend`), a `Makefile` with a `quickstart` target chaining
`fetch-data → build-index → run → pull-model`, and three new test scripts
covering the failure modes this sprint specifically had to guard against
(below).

## Ollama is containerized (`ollama/ollama` image), not host-native

The prior dev setup used a host-installed Ollama; that's a one-machine
solution, not a bootstrap anyone can clone and run. `ollama_data` (a named
volume, `/root/.ollama`) persists pulled models across restarts; the
container itself always starts empty — `make pull-model` (`docker compose
exec ollama ollama pull mistral`) pulls the model explicitly, matching
`src/generation/generate.py`'s `DEFAULT_MODEL = "ollama_chat/mistral"`.

**CPU-only inference by default** — no GPU passthrough is configured in
`docker-compose.yml`. This is adequate for this project's portfolio-demo
scope; it is explicitly not a production performance target, and anyone
adding GPU passthrough later should expect to add the corresponding
`deploy.resources.reservations.devices` block themselves. The same
CPU-only reasoning was applied to the `api` image's own torch dependency
(pulled in transitively by `sentence-transformers` for the dense embedder
and cross-encoder reranker, `src/indexing/embeddings.py`,
`src/retrieval/reranking.py`): PyPI's default `linux/*` torch wheel bundles
~4GB of unused CUDA/triton libraries, so `pyproject.toml` pins Linux
specifically to the `pytorch-cpu` package index (`tool.uv.sources.torch`,
marker-scoped to `sys_platform == 'linux'`); macOS/Windows dev installs are
unaffected. `torch` had to be promoted to a direct
`[project.dependencies]` entry for the marker-scoped source to take effect
at all — `uv`'s `tool.uv.sources` overrides apply to packages your own
`pyproject.toml` requests directly, not to a name that only ever shows up
transitively.

## CRITICAL: `VITE_API_BASE` must be a browser-reachable URL, baked in at build time

The frontend runs in the user's browser, never inside the Docker network —
`frontend/src/api/client.ts`'s `import.meta.env.VITE_API_BASE` has to
resolve to something the browser can actually reach
(`http://localhost:8000`, the `api` service's host-mapped port), never the
internal Docker service name (`http://api:8000`), which only resolves
container-to-container. Because Vite inlines `import.meta.env.*` into the
bundle at build time — there is no runtime env lookup once the JS ships —
`VITE_API_BASE` is passed as a Docker build `ARG` in `frontend/Dockerfile`
and set in `docker-compose.yml`'s `frontend.build.args`, not as a
container `environment:` entry (which would have zero effect on
already-baked JS).

Getting this backwards is a genuinely silent failure mode: the image still
builds, the container still starts and serves a page, and a
container-only check (curl the frontend, get a 200) still passes — it only
breaks once a real browser tries to call the internal service name, which
never resolves outside the Docker network. `scripts/test_frontend_arg.sh`
exists specifically to catch this class of mistake: it fetches the
frontend's *served* JS bundle (post-build, from the running nginx
container, not just the local `dist/` output) and asserts it contains the
host-facing URL and never the internal service name.

## Healthchecks and startup ordering

`qdrant` and `ollama` both get `healthcheck:` entries and `api` depends on
both via `condition: service_healthy` (not just container-start order) —
this closes a real race where `api` could otherwise start serving before
Qdrant/Ollama are actually ready to accept requests. Neither base image
ships `curl`/`wget` (qdrant's Debian-slim base has bash but no HTTP
client; ollama's image has neither), so `qdrant`'s check is a raw HTTP/1.1
request over bash's `/dev/tcp`, and `ollama`'s check is `ollama list`
itself (a real client call to the local server, succeeds as soon as it
responds — even with zero models pulled). `api` gets its own
`HEALTHCHECK` too (`curl -f localhost:8000/docs`, defined in `Dockerfile`
since `curl` is already installed there for
`scripts/test_container_connectivity.sh`'s container-to-container checks),
and `frontend` depends on it the same way — so `docker compose up --build`
converges to all-healthy with no service having raced ahead of a
dependency it needed.

## CORS

`src/api/main.py`'s `FRONTEND_DEV_ORIGIN` (the Vite dev server,
`http://localhost:5173`) stays hardcoded and always-allowed, so `npm run
dev` keeps working against either a host-native or a dockerized `api`.
The dockerized frontend's own origin (`http://localhost:3000`, nginx's
host-mapped port) is added on top via a new `CORS_ORIGINS` env var
(comma-separated, additive), set in `docker-compose.yml`'s
`api.environment`.

## Internal vs. browser-facing URLs — the two directions, and the two tests that guard each one

`api`'s own outbound calls to Qdrant/Ollama *should* use internal Docker
service names (`QDRANT_URL=http://qdrant:6333`,
`OLLAMA_API_BASE=http://ollama:11434`) — that's correct,
container-to-container traffic. Note the second one is `OLLAMA_API_BASE`,
not a generic `OLLAMA_URL`: LiteLLM's `ollama_chat` provider
(`src/generation/generate.py`'s `DEFAULT_MODEL`) specifically reads
`OLLAMA_API_BASE` (`litellm/llms/ollama/common_utils.py`) — setting a
differently-named env var would silently do nothing and leave every
generate/judge call falling back to `localhost:11434`, i.e. the `api`
container itself. `scripts/test_container_connectivity.sh` (`docker
compose exec api curl qdrant:6333/healthz` / `ollama:11434/`) checks this
direction. The frontend's `VITE_API_BASE` is the mirror-image case in the
opposite direction — see above, and `scripts/test_frontend_arg.sh`.

## Makefile — actual dependency order implemented

`fetch-data → build-index → run → pull-model` (`quickstart` chains
exactly this). `build-index` must follow `fetch-data` (it ingests
`data/raw/corpus`, which doesn't exist until fetched) and precede a
*useful* `run` (an `api` container against an empty Qdrant collection
starts and passes its healthcheck fine, it just has nothing to retrieve).
`build-index` itself runs Sprint 1 ingestion + Sprint 2 indexing on the
**host** via `uv run` (not inside a container — these scripts need the
dev venv's spaCy model, and reach Qdrant over its published host port),
starting `qdrant` alone first if it isn't already running. `pull-model`
only needs the `ollama` container started, which `run` already
guarantees; it's last in the chain, but nothing actually breaks if it runs
any time after `run` and before a real `/generate` call — `api`'s own
healthcheck (`GET /docs`) never calls the LLM, so `api` starts and reports
healthy whether or not a model has been pulled yet.

## Observed CPU-only latency, and why it's slower than pre-Sprint-9 dev

Verified end-to-end against this sprint's own stack (`docker compose up
--build`, real `fetch-data`/`build-index` history already on disk, `make
pull-model`): `/retrieve` and `/generate` both work, but a cold
`/generate` call — `ollama_chat/mistral` on CPU inside Docker Desktop's
VM, `ollama ps` showing ~400% CPU (four cores) — took several minutes end
to end, well past a naive 120s client timeout
(`scripts/smoke_test.py` uses 600s specifically because of this).
Concurrent/overlapping requests during the same cold-start window made
things markedly worse (observed 5–6GB RSS and multi-minute additional
stalls when a second `/retrieve` landed while the first was still loading
BGE-M3/the reranker) — restarting the `api` container to clear any
piled-up in-flight requests resolved it.

The root cause, on Apple Silicon specifically: neither
`src/indexing/embeddings.py`'s `DenseEmbedder` nor
`src/retrieval/reranking.py`'s `CrossEncoderReranker` pins a device —
`sentence-transformers` auto-detects the best backend, which on a native
macOS host means Apple's Metal (MPS), automatically accelerating both the
BGE-M3 embedder and the cross-encoder reranker. Native Ollama does the
same for generation. Inside `docker compose`'s containers, none of that is
reachable: Docker Desktop's Linux VM has no Metal passthrough (unlike
`nvidia-container-toolkit` on a Linux host), so every one of these
silently falls back to CPU — no error, just slow — inside a VM whose whole
resource pool is also capped well below the host's own (observed ~7.75GB
total across all four containers, vs. direct access to the full host on a
native run). None of this is a bug to fix here; it's the direct, expected
cost of "CPU-only, no GPU passthrough" at this project's demo scope, and
worth knowing before assuming a hung request is broken rather than just
slow. `README.md`'s "Faster local dev" section documents the native
alternative (Qdrant containerized, everything else run directly on the
host) for anyone iterating locally on Apple Silicon rather than validating
the bootstrap path itself.

A secondary, fixable cost stacked on top of the above during this
session's own testing: the `api` container had no persistent model cache,
so BGE-M3/the reranker (several GB) re-downloaded from Hugging Face on
every container recreation. Fixed by adding an `hf_cache` named volume
(`/root/.cache/huggingface`) to the `api` service in `docker-compose.yml`
— weights now survive `docker compose restart`/`up` (though not a full
`down -v`, same as `qdrant_data`/`ollama_data`), so only the very first
run after a fresh `docker compose up --build` pays the download cost.

## Tests

`scripts/test_frontend_arg.sh` (the build-ARG regression test, above) and
`scripts/test_container_connectivity.sh` (the reverse direction) both run
against an already-up stack. `scripts/smoke_test.py` is the end-to-end
check: gold-dataset query Q002 through the running stack's `/retrieve`
then `/generate`, asserting a gold `chunk_id` (`eval/gold_dataset.csv`'s
`1907_EC_c9` / `1907_EC_c163` / `1934_PM_c6`) was actually retrieved and
that generation produced a non-empty answer — confirming corpus fetch,
indexing, all four services, and the pulled model actually work together,
not just that each piece works in isolation. `make test-frontend-arg` /
`make test-connectivity` / `make smoke-test` wrap all three.
