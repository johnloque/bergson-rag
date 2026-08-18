# Backend API (Sprint 7a, `feat/api-endpoints`)

FastAPI scaffold in `src/api/`: `POST /retrieve`, `POST /generate`, `POST
/evaluate`, `POST /judge-chunk`. Each is a thin wrapper around an existing,
already-tested function — `hybrid_search` + `rerank`, `generate_from_chunks`,
`generate_evaluation` + `should_auto_expand`, and `judge_chunk` respectively
— no retrieval, generation, evaluation, or judging logic is reimplemented at
this layer. Request/response bodies are Pydantic models (`src/api/schemas.py`);
a malformed body is rejected with a 422 and a field-level error rather than
reaching the wrapped function at all.

## No persistence yet

No persistence, no session/conversation history yet (`feat/api-persistence`,
still pending, not part of this sprint's deliverable): every request is
self-contained, and a caller resends whatever chunk content it needs across
calls (`ChunkInput`, `src/api/schemas.py`) — typically the (possibly
user-curated) output of a prior `/retrieve` call — rather than the server
looking anything up by a prior request's ID.

## Known simplification, not a bug to fix on this branch

`/evaluate` has no server-side record of a prior `/generate` call, so it
trusts whatever `(query, chunks, answer)` triple the client submits as-is —
there is no check that `answer` actually came from generating on those exact
`chunks`. `/generate` and `/evaluate` are deliberately kept as two separate
HTTP calls rather than one combined, blocking endpoint: this is what lets the
client render the draft answer immediately and apply Sprint 6's
collapsed-by-default / auto-expand-on-good-evaluation UI behavior only once
evaluation resolves. The two-call shape is intentional; the missing piece —
verifying server-side that a given `/evaluate` call's input really is the
output of an earlier `/generate` call — is exactly what `feat/api-
persistence` resolves, once generations are actually stored somewhere the
server can check against.

## Provider failures and CORS

LLM-provider failures (e.g. a local Ollama server not running — a real,
already-encountered failure mode in this project's own dev workflow, not a
hypothetical) surface as a 503 naming the failed provider and model, rather
than an unhandled 500. CORS is enabled for a single hardcoded local Vite dev
origin (`http://localhost:5173`), ahead of Sprint 8's frontend needing it.

## Test coverage

`tests/test_api.py`, same real-corpus / gold-dataset fixture discipline as
`tests/test_guardrail.py` and `tests/test_chunk_judge.py`, plus
malformed-body (422) and simulated-provider-failure (503) coverage for every
endpoint.
