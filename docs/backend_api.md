# Backend API and persistence (Sprint 7, `feat/api-endpoints` + `feat/api-persistence`)

FastAPI scaffold in `src/api/`: `POST /retrieve`, `POST /generate`, `POST
/evaluate`, `POST /judge-chunk`, `GET /turns/{id}`, `GET /conversations/{id}`.
Each compute endpoint is a thin wrapper around an existing, already-tested
function — `hybrid_search` + `rerank`, `generate_from_chunks`,
`generate_evaluation` + `should_auto_expand`, and `judge_chunk` respectively
— no retrieval, generation, evaluation, or judging logic is reimplemented at
this layer. Request/response bodies are Pydantic models (`src/api/schemas.py`);
a malformed body is rejected with a 422 and a field-level error rather than
reaching the wrapped function at all.

## Persistence (Sprint 7b)

SQLModel over a single local SQLite file (`data/app.db` by default,
`BERGSON_DB_PATH` overrides it — gitignored like every other generated data
artifact in this project, runtime state, not source). SQLModel was chosen
over raw `sqlite3` or a heavier ORM because it pairs naturally with
FastAPI's existing Pydantic models rather than hand-rolling a second
validation layer — the same "reuse a fit-for-purpose library" discipline
this project already applies to LiteLLM and RAGAS.

Schema (`src/api/models.py`):

- `conversations(id, created_at)`
- `turns(id, conversation_id, query, created_at)`
- `retrieved_chunks(turn_id, chunk_id, rank, score)` — one row per chunk
  shown to the user for a turn. Replaced wholesale on each `/generate` call
  against that turn, not accumulated, since a regeneration may curate a
  different chunk selection than the initial call.
- `generations(id, turn_id, model, chunk_ids, answer, chunk_judgments_used,
  created_at)`
- `evaluations(id, generation_id, structural_flags, faithfulness_annotations,
  retrieval_confidence_tier, should_auto_expand, created_at)`
- `chunk_judgments(turn_id, chunk_id, label, justification, model,
  created_at)` — composite primary key `(turn_id, chunk_id)`, upsert
  semantics: a chunk judged twice in the same turn overwrites, never
  accumulates duplicate rows.

### Accepted limitation: chunk text is not snapshotted

`retrieved_chunks` stores only `chunk_id`, `rank`, and `score` — never the
chunk's text, work_id, or section_path. If the corpus is later reindexed, a
historical turn's chunk references could point to content that has since
changed. `/evaluate` and `GET /turns/{id}` both re-fetch chunk content live
from Qdrant by `chunk_id` (`src/api/converters.py:fetch_chunk_input`)
instead of reading a stored snapshot: `/evaluate` drops a chunk_id no longer
indexed from the reconstructed set rather than raising, and `GET
/turns/{id}` returns it with empty text/work_id/section_path fields (the
frontend renders its own placeholder for that case, `frontend/src/state/
chunkCache.ts`). Accepted for this single-user local portfolio demo:
snapshotting full chunk text for every turn is unnecessary storage cost
here, not solved on this branch.

## `/generate`'s turn/conversation and chunk_judgments rules

- No `turn_id`: creates a new turn (and a new conversation, if
  `conversation_id` is also absent). `turn_id` present: a regeneration
  within that existing turn (404 if unknown).
- `chunk_judgments` explicitly provided in the request (including an empty
  dict) is used as-is and overrides any persisted judgments for that turn.
  Omitted (or explicit `null`) AND `turn_id` provided -> the server
  auto-loads that turn's persisted `chunk_judgments` as the default — this
  is what lets a plain "regenerate" click work without the client resending
  every judgment it already made.
- Response gains `generation_id`, `turn_id`, `conversation_id`.

## Two risks this branch resolves

Sprint 7a shipped the four compute endpoints with no persistence, and
flagged two risks as deferred rather than solved:

1. **`/evaluate` trusted a client-submitted `(query, chunks, answer)`
   triple**, with no server-side proof it came from a real `/generate`
   call. Resolved: `/evaluate` now takes `{generation_id}` and looks the
   generation up in the DB — `query` and `answer` come from the stored
   record, not the client (chunk text is still re-fetched live from Qdrant,
   see the limitation above — but the `(answer, chunks)` pairing itself can
   no longer be fabricated). Unknown `generation_id` -> 404. `/generate`
   and `/evaluate` remain two separate HTTP calls, unchanged from Sprint
   7a: this is still what lets the client render the draft answer
   immediately and apply Sprint 6's collapsed-by-default /
   auto-expand-on-good-evaluation UI behavior only once evaluation
   resolves.
2. **A user who left before `generate_evaluation` completed, or before a
   session persisted, never saw the final badge state** (`should_auto_expand`,
   faithfulness annotations) — Sprint 6's flagged risk. Resolved:
   `GET /turns/{turn_id}` reassembles a turn's full state (query, retrieved
   chunks, generation(s), evaluation(s), chunk judgments) purely from
   persisted rows — no Qdrant/LLM dependency — so a reloaded page recovers
   it even if the live session, or the retrieval/generation stack itself,
   is gone. `GET /conversations/{id}` returns just the list of turns (id,
   query, created_at) in a conversation, enough for a history sidebar
   later (Sprint 8) — use `GET /turns/{id}` for full per-turn detail.

## Provider failures and CORS

LLM-provider failures (e.g. a local Ollama server not running — a real,
already-encountered failure mode in this project's own dev workflow, not a
hypothetical) surface as a 503 naming the failed provider and model, rather
than an unhandled 500. CORS is enabled for a single hardcoded local Vite dev
origin (`http://localhost:5173`), ahead of Sprint 8's frontend needing it.

## Test coverage

`tests/test_api.py`: same real-corpus / gold-dataset fixture discipline as
`tests/test_guardrail.py` and `tests/test_chunk_judge.py`, plus
malformed-body (422) and simulated-provider-failure (503) coverage for every
endpoint. `tests/test_persistence.py`: the `/generate` -> `/judge-chunk` ->
`/generate` round trip (a persisted judgment auto-loaded into a
regeneration's prompt), the `chunk_judgments` override rule, `/evaluate` via
direct DB insertion of a generation record (Q001/Q004 confirmed-
hallucination fixtures, bypassing a live `/generate` call so it stays fast
and independent of model output variance), `GET /turns/{id}` and
`GET /conversations/{id}` assembling persisted state correctly after a full
generate -> evaluate -> judge-chunk sequence, and 404s on every id-keyed
lookup. Each test gets its own isolated in-memory SQLite DB via
`app.dependency_overrides[get_session]`, so persisted rows never leak
between tests or touch the real dev database.
