# CI (`ci/fast-workflow`)

`.github/workflows/ci.yml` runs lint + a fast test suite on every push and
every pull request, on all branches (`on: [push, pull_request]`) — the
point is to catch breakage as early as the branch itself, not just at PR
time. Two parallel jobs, `backend` and `frontend`, each independently
blocking.

No Qdrant, no Ollama, no deployment step: this workflow only verifies the
code is correct and well-formed, not that the full retrieval/generation
pipeline produces good answers against the real corpus — that's a
separate, slower concern (see "Not yet covered" below).

## Why a fast/slow split exists

`docs/dockerization.md`'s "Ollama: native by default, containerized
opt-in" section already diagnosed the underlying constraint this
workflow inherits: Docker Desktop on Apple Silicon has no Metal/GPU
passthrough, so any containerized model call — Ollama generation, the
`bge-reranker-v2-m3` cross-encoder, the `bge-m3` dense embedder, BM25
sparse embedding via `fastembed` — runs CPU-only and is measured at
3-5x slower than native. A GitHub Actions `ubuntu-latest` runner is the
same story, minus even the option of a native fallback: it's a shared,
ephemeral CPU-only VM with no GPU and no already-running Ollama/Qdrant
service to attach to. Standing up both from scratch on every run (pull
the corpus, build the index, pull an Ollama model, wait out CPU-only
inference for a run's worth of gold-dataset queries) would cost several
minutes *per push*, dominated by model I/O rather than by anything this
workflow is actually trying to catch.

So: tests that call a real model (generation, the judge, the reranker,
either embedder) or that require a live, populated Qdrant collection are
excluded from the default CI run entirely, rather than tolerated at that
cost. They still run — just not here; see "Not yet covered" below.

## The `slow` marker

`pyproject.toml`'s `[tool.pytest.ini_options]` registers one marker:

```toml
markers = [
    "slow: requires a real model call and/or a live Qdrant collection — excluded from the fast CI workflow",
]
```

Any test decorated `@pytest.mark.slow` (or, for a module where every test
qualifies, a module-level `pytestmark` including `pytest.mark.slow`) is
skipped by the CI workflow's `uv run pytest -m "not slow"` — see
`tests/test_generation.py`, `tests/test_guardrail.py`, etc. for the
worked examples of both the per-test and whole-module forms.

**What counts as slow:** a test that calls `litellm.completion`/
`acompletion` against a real generation or judge model, that constructs
a real `CrossEncoderReranker`/`DenseEmbedder`/`SparseEmbedder` and
actually runs it, or that needs a live, reachable Qdrant instance (to
read back real chunk content, run `hybrid_search`, or index/query a
collection) — including a test that only *reads* Qdrant to resolve a
chunk (`GET /turns/{id}`'s chunk re-fetch is the same dependency as a
full retrieval call, even though it doesn't call `hybrid_search`
itself).

**What doesn't:** pure logic with no model/Qdrant dependency — XML
parsing (`tests/test_ingestion.py`), RRF fusion math and other hand-built
`RetrievedChunk` fixtures, prompt-construction string assertions
(`tests/test_prompt.py`), golden prompt snapshots, the prompt loader and
`prompts_used` columns (`tests/test_prompt_snapshots.py`,
`tests/test_prompt_loader.py`, `tests/test_prompts_used.py`, LLMs mocked —
see `docs/prompts.md`), `resolve_paragraph_metadata`/
`should_auto_expand` gating logic, citation/title-fabrication regex
checks, gold-dataset CSV parsing. These run in both the fast suite and
the full suite, unconditionally (modulo their own, pre-existing
`skipif`s for local data files like `data/raw/corpus` or
`data/processed/chunks`, which is a different, local-build-artifact
concern — see "Not yet covered").

**Local behavior is unchanged.** `uv run pytest` with no arguments still
runs the full suite, slow tests included, exactly as before this branch
— the `-m "not slow"` filter is applied only by the CI workflow's own
invocation (`uv run pytest -m "not slow"`), never baked into
`pyproject.toml`'s pytest defaults. A developer running the suite
locally (with Qdrant/Ollama up) still gets full coverage by default.

## What the `backend` job runs

- `uv sync` — installs from `uv.lock`.
- `uv run ruff check .` — lint.
- `uv run ruff format --check .` — formatting compliance, matching the
  `ruff-format` pre-commit hook already configured in
  `.pre-commit-config.yaml`. `ruff` is pinned in `pyproject.toml`'s dev
  dependency group (`ruff==0.6.9`) to the exact version
  `.pre-commit-config.yaml`'s `ruff-pre-commit` rev uses — an unbounded
  `ruff>=0.6` here would let `uv sync` resolve whatever's latest, whose
  formatter can disagree with the pre-commit-pinned version on
  already-compliant code (observed directly while building this
  workflow: several already-formatted test files were flagged as
  "would reformat" under a newer ruff purely from formatter-output
  drift, not any actual style violation). Bump both pins together when
  upgrading ruff.
- `uv run pytest -m "not slow"` — the fast suite.

## What the `frontend` job runs

All steps run with `working-directory: frontend`.

- `npm ci` — installs from `frontend/package-lock.json`.
- `npm run lint` (`oxlint`) — fails the job on an `error`-level rule
  violation; `warn`-level findings (e.g. the `react/only-export-components`
  rule) print but don't fail the build, which is `oxlint`'s own default
  and not something this workflow overrides.
- `npm run test` (`vitest run`) — unit tests.
- `npm run build` (`tsc -b && vite build`) — a real compile, not just
  unit tests. This is what catches a TypeScript type error that no unit
  test happens to exercise, and that would otherwise only surface at
  deploy time.

## Not yet covered

- **The slow-test workflow itself.** Running `-m slow` in CI would need
  a Qdrant service (`services:` in the workflow, or a
  `docker compose up qdrant` step) with the collection actually built
  (`scripts/build_index.py`, which itself needs the corpus fetched and
  chunked first) and a reachable generation/judge model. That's a
  meaningfully heavier, separate piece of infrastructure — tracked as a
  follow-up branch, not part of `ci/fast-workflow`.
- **Deployment.** This workflow only verifies the code; it doesn't build
  or push any image, and doesn't touch `docker-compose.yml`.
- **Branch protection.** Adding this workflow does not, by itself, block
  a bad merge — see the manual follow-up step below.

## Manual follow-up (not automatable from the repo)

Once this branch is merged, enable **Settings → Branches → Branch
protection rules → main → Require status checks to pass before
merging**, and select the `backend` and `frontend` jobs. Until that's
done, the workflow runs and reports status on every push/PR, but a
failing check doesn't actually prevent a merge — this step is what makes
it load-bearing rather than advisory. It has to be done from the GitHub
UI/API, not from within the repository.
