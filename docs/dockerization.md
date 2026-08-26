# Dockerization and bootstrap (Sprint 9)

Four services in `docker-compose.yml` (`qdrant`, `ollama`, `api`,
`frontend`), a `Makefile` with a `quickstart` target chaining
`fetch-data → build-index → setup-ollama → run`, and three new test
scripts covering the failure modes this sprint specifically had to guard
against (below).

**Amended by `fix/ollama-native-default`** — see "Ollama: native by
default, containerized opt-in" below. Sprint 9 originally containerized
Ollama by default; that decision is superseded. The rest of this
document (healthchecks, CORS, the internal-vs-browser-facing URL split,
the Makefile dependency order rationale, the frontend build-ARG test)
still describes the current, shipped behavior.

## Ollama: native by default, containerized opt-in (`fix/ollama-native-default`)

**The finding.** Docker Desktop on Apple Silicon has no Metal (GPU)
passthrough into its Linux VM — unlike `nvidia-container-toolkit` on a
Linux host, there is no equivalent path for Apple's GPU. A container's
Ollama process is therefore always CPU-only, regardless of anything in
`docker-compose.yml`. Measured against native host Ollama (which
`sentence-transformers`/Ollama both pick up automatically via Metal/MPS)
on the same machine, containerized generation was **~3-5x slower**,
consistent with the multi-minute cold-generate times logged in "Observed
CPU-only latency" below. This supersedes Sprint 9's original decision to
containerize Ollama by default — that decision optimized for
"one-command bootstrap," but paid for it with a GPU-passthrough
limitation that a from-scratch clone-and-run flow shouldn't default into
on the platform this project is actually developed on.

**The fix: split the fast default from the portable fallback**, instead
of picking one:

- **Native Ollama is now the default path** (`make setup-ollama`,
  `scripts/setup_ollama.sh` — not Docker-based). Fast, Metal-accelerated
  on Apple Silicon, same as the pre-Sprint-9 dev flow.
- **Containerized Ollama becomes an explicit, opt-in fallback**, gated
  behind a Compose profile (`profiles: ["with-ollama"]` on the `ollama`
  service in `docker-compose.yml`) so a plain `docker compose up` /
  `make run` does **not** start it. It's still there for anyone without a
  usable host Ollama install (e.g. CI, a Linux box without `sudo`, a
  quick one-off clone) — started explicitly with `docker compose
  --profile with-ollama up` / `make run-with-ollama`. Still CPU-only,
  still the slower path — that tradeoff is now opt-in and named, not the
  silent default.

**The mechanism — `OLLAMA_API_BASE` is now environment-configurable**,
not hardcoded to the internal service name. `docker-compose.yml`'s
`api.environment.OLLAMA_API_BASE` defaults to
`http://host.docker.internal:11434` (native host Ollama — Docker
Desktop resolves this automatically on Mac/Windows; an `extra_hosts:
host.docker.internal:host-gateway` entry was added to the `api` service
so it also resolves on native Linux Docker Engine, which doesn't wire it
up by default). `make run-with-ollama` overrides it to
`http://ollama:11434` (the internal Docker service name) when the
`with-ollama` profile is active — this override is necessary, not just
documentation: Compose does not recreate `api` just because a profile
service it doesn't directly depend on started, so without the explicit
override `api` would still be pointed at `host.docker.internal` even
with the `ollama` container up and healthy. `api`'s own `depends_on:
ollama` carries `required: false` (Compose ≥2.20 syntax) specifically so
this is legal either way — with the profile inactive, the dependency is
skipped entirely (no error, no wait); with it active, `api` still waits
for `ollama`'s healthcheck before starting, same as before this branch.

Both directions were verified live: with only `qdrant`/`api`/`frontend`
up (native mode, no `ollama` container running at all), `docker compose
exec api curl http://host.docker.internal:11434/` reaches a real
Ollama process running directly on the host. With `--profile
with-ollama up` and `OLLAMA_API_BASE=http://ollama:11434`,
`docker compose exec api curl http://ollama:11434/` reaches the
container instead. `scripts/test_container_connectivity.sh` now
auto-detects which mode is active (whether the `ollama` service
container is running) and checks the corresponding target — see
"Tests" below.

**`ollama_data` (a named volume, `/root/.ollama`) still persists pulled
models across restarts** for the containerized path; the container
itself always starts empty — `make run-with-ollama` pulls the model
explicitly into it (`docker compose exec ollama ollama pull mistral`),
matching `src/generation/generate.py`'s `DEFAULT_MODEL =
"ollama_chat/mistral"`. The native path pulls into the host's own Ollama
model store instead, via `scripts/setup_ollama.sh` (`ollama pull
mistral`), verified at the end with a real generation request/response —
not just a successful pull exit code, which would miss a
pulled-but-unloadable model or a server that accepts connections but
can't actually serve.

**CPU-only inference remains the default for the containerized fallback
path specifically** — no GPU passthrough is configured for the `ollama`
service in `docker-compose.yml`, and (per the finding above) none is
achievable on Docker Desktop/Apple Silicon regardless. Anyone running the
containerized path on a Linux host with an NVIDIA GPU could add the
corresponding `deploy.resources.reservations.devices` block themselves —
not done here, since the native path is the intended fast route on any
platform where GPU acceleration matters for this project. The same
CPU-only reasoning was separately applied to the `api` image's own torch dependency
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

`qdrant` and `ollama` both get `healthcheck:` entries. `api` depends on
`qdrant` unconditionally via `condition: service_healthy` (not just
container-start order); it depends on `ollama` the same way but with
`required: false` (`fix/ollama-native-default` — see above), so the
dependency is skipped entirely when the `ollama` service isn't part of
the active profile (the default, native-Ollama mode) and only actually
gates startup when `--profile with-ollama` is active. Either way, this
closes a real race where `api` could otherwise start serving before
Qdrant (or containerized Ollama, when in use) is actually ready to accept
requests. Neither base image ships `curl`/`wget` (qdrant's Debian-slim base has bash but no HTTP
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

`api`'s own outbound call to Qdrant *should* use the internal Docker
service name (`QDRANT_URL=http://qdrant:6333`) — that's correct,
container-to-container traffic, always. Its call to Ollama is
environment-configurable (`fix/ollama-native-default` — see above):
`OLLAMA_API_BASE` defaults to `http://host.docker.internal:11434`
(native host Ollama) and is overridden to `http://ollama:11434` (the
internal service name) specifically when `make run-with-ollama` is used.
Note it's `OLLAMA_API_BASE`, not a generic `OLLAMA_URL`: LiteLLM's
`ollama_chat` provider (`src/generation/generate.py`'s `DEFAULT_MODEL`)
specifically reads `OLLAMA_API_BASE` (`litellm/llms/ollama/common_utils.py`)
— setting a differently-named env var would silently do nothing and leave
every generate/judge call falling back to `localhost:11434`, i.e. the
`api` container itself. `scripts/test_container_connectivity.sh` checks
this direction for whichever mode is active — `docker compose exec api
curl qdrant:6333/healthz` always, plus either
`host.docker.internal:11434/` (native, default) or `ollama:11434/`
(containerized, `with-ollama` profile), auto-detected from whether the
`ollama` service container is running. The frontend's `VITE_API_BASE` is
the mirror-image case in the opposite direction — see above, and
`scripts/test_frontend_arg.sh`.

## Makefile — actual dependency order implemented

`fetch-data → build-index → setup-ollama → run` (`quickstart` chains
exactly this). `build-index` must follow `fetch-data` (it ingests
`data/raw/corpus`, which doesn't exist until fetched) and precede a
*useful* `run` (an `api` container against an empty Qdrant collection
starts and passes its healthcheck fine, it just has nothing to retrieve).
`build-index` itself runs Sprint 1 ingestion + Sprint 2 indexing on the
**host** via `uv run` (not inside a container — these scripts need the
dev venv's spaCy model, and reach Qdrant over its published host port),
starting `qdrant` alone first if it isn't already running. `setup-ollama`
(`scripts/setup_ollama.sh`, `fix/ollama-native-default` — not
Docker-based) installs/starts native host Ollama and pulls `mistral` into
it; nothing actually breaks if it runs any time before a real
`/generate` call rather than strictly before `run` — `api`'s own
healthcheck (`GET /docs`) never calls the LLM, so `api` starts and
reports healthy whether or not a model has been pulled yet — but it's
ordered before `run` in `quickstart` so the chain leaves a fully working
stack with no follow-up step required. The containerized fallback path
(`make run-with-ollama`) has its own self-contained order instead:
`docker compose --profile with-ollama up -d --build` (with
`OLLAMA_API_BASE=http://ollama:11434` set for that invocation) then
`docker compose exec ollama ollama pull mistral` — it isn't part of
`quickstart`, since native is the default.

## Observed CPU-only latency (containerized path) — the measurement behind `fix/ollama-native-default`

This is the original Sprint 9 measurement, taken against the
then-fully-containerized stack, that motivated superseding "containerize
Ollama by default" — see "Ollama: native by default, containerized
opt-in" above for the fix and the ~3-5x native-vs-containerized
comparison. It still applies as-is to today's opt-in `with-ollama`
fallback path.

Verified end-to-end (`docker compose --profile with-ollama up --build`,
real `fetch-data`/`build-index` history already on disk, `docker compose
exec ollama ollama pull mistral`): `/retrieve` and `/generate` both work, but a cold
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

**`fix/ollama-native-default` coverage.** `test_container_connectivity.sh`
now covers both Ollama modes from one script, auto-detecting which is
active (see "Internal vs. browser-facing URLs" above) — this is what
actually proves `OLLAMA_API_BASE` is consumed at runtime rather than
hardcoded to one value, since the same script asserts a different
reachable target depending on which mode is up. `smoke_test.py` needed no
changes to cover both paths: it only talks to `api`'s published port, so
the same Q002 end-to-end check exercises whichever backend `api` was
actually configured to reach — run once against `make run` (native) and
once against `make run-with-ollama` (containerized) to confirm generation
actually works through both. Verified live during this branch's own
implementation: `docker compose exec api curl
http://host.docker.internal:11434/` succeeded against a real native
`ollama serve` process with no `ollama` container running at all, and
`docker compose exec api curl http://ollama:11434/` succeeded separately
against the containerized service with `OLLAMA_API_BASE` overridden —
confirming the mechanism itself, independent of the model-pull time a
full Q002 run would add.
