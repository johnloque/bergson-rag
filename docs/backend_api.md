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

**Superseded by Sprint 10** (`fix/turn-lifecycle-and-manual-generation`,
[`docs/turn_lifecycle.md`](turn_lifecycle.md)): turn/conversation creation
moved to `/retrieve`. `POST /retrieve` now takes an optional
`conversation_id` (absent creates a new conversation) and returns
`turn_id`/`conversation_id` alongside `chunks`, persisting the turn and its
retrieved chunk set immediately. `POST /generate`'s `turn_id` is now
**required** — it never creates a turn itself, whether this is the turn's
first, manually-triggered generation or a later regeneration (404 if
unknown) — and `query` is no longer part of the request body; it's read
back from the persisted turn instead. The rules below otherwise stand:

- `chunk_judgments` explicitly provided in the request (including an empty
  dict) is used as-is and overrides any persisted judgments for that turn.
  Omitted (or explicit `null`) -> the server auto-loads that turn's
  persisted `chunk_judgments` as the default — this is what lets a plain
  "regenerate" click work without the client resending every judgment it
  already made.
- Response gains `generation_id`, `turn_id`, `conversation_id`.

## Retrieval filtering: `work_ids` + `date_range` (Sprint 11, `feat/retrieval-filtering`)

`POST /retrieve` takes two independent, combinable filters, both applied
*before* reranking (the same candidate-selection stage a plain,
unfiltered call runs at — filtering never costs recall relative to an
unfiltered call, and never shrinks the final `top_k` result below what an
unfiltered call would return, aside from genuinely running out of
in-range candidates):

- `work_ids: [str]` — a plain allowlist, applied as a native Qdrant
  payload filter on the already-indexed `work_id` field.
- `date_range: {start: int, end: int, mode: "publication" | "text"}` —
  `mode` defaults to `"publication"`, so a caller that never sets
  `date_range` at all, or sets it without an explicit `mode`, sees
  unaffected/pre-Sprint-11 behavior.

Combination semantics: when both are given, a chunk must match an allowed
`work_id` **and** an allowed date (intersection, not union). An empty
`work_ids: []` is a valid, deliberately-empty allowlist (matches nothing),
distinct from omitting `work_ids` entirely (no restriction).

Neither mode adds a year field to the Qdrant payload — this project has
deliberately kept title/year as a separate lookup (`src/works.py`), never
duplicated into the vector store, to avoid a second source of truth
needing resync on every correction; date filtering stays a query-time
lookup into `src/works.py` in both modes.

### `"publication"` mode (default)

Translates `date_range` into the set of work_ids whose *work-level*
publication year (`src.works.WORKS` — identical for all 8 works, including
1919_ES/1934_PM: their parent anthology's own publication year, never an
individual text's) falls in range, then applies that set as the same kind
of native `work_id` Qdrant filter `work_ids` itself uses. Cheap, exact, no
recall loss — Qdrant decides the eligible candidate set before dense/sparse
search even runs.

### `"text"` mode (opt-in)

For 1919_ES and 1934_PM specifically, filters at the *individual text*
level instead: `src.works.resolve_paragraph_metadata`'s `text_year` when a
chunk's paragraph falls inside one of those works' individually-dated texts
(`src.works.TEXTS`), falling back to `work_year` for any paragraph not
covered by a dated text (e.g. 1934_PM's front matter, paragraphs 1-3). For
the other 6 works, `"text"` mode is identical to `"publication"` mode —
`resolve_paragraph_metadata` always returns `text_year=None` for them, so
their effective year is always the work-level year either way.

This can't be expressed as a single native Qdrant filter without
duplicating year data into the payload (ruled out above), so it's
implemented as a genuine post-retrieval filter (`src/retrieval/filtering.py:
matches_date_range`) — applied to the candidate set *before* reranking, not
after, so a match doesn't get silently dropped by the reranker's own
candidate-pool cutoff.

**Recall-preservation mechanism.** Filtering after Qdrant's own top-N
prefetch cutoff can drop otherwise-well-ranked candidates and shrink the
final result below the requested `top_k`. To avoid this, `date_range` in
`"text"` mode first partitions 1919_ES/1934_PM into three buckets
(`src.retrieval.filtering.partition_anthology_works`), computed from each
work's set of individually-dated-text years plus its own publication year:

- **Fully included** — every chunk's effective year is already known to be
  in range (e.g. a range spanning 1901-1919 covers all of 1919_ES's dated
  texts, 1901-1913, and its own 1919 publication year). Folded into the
  same cheap native `work_id` filter as any other eligible work — no
  post-filtering needed.
- **Fully excluded** — no chunk's effective year can be in range. The work
  is simply left out of the Qdrant query entirely.
- **Needs post-filtering** — the range excludes some but not all of the
  work's individually-dated texts (the only case that actually risks
  recall loss). For exactly this bucket, the work is *not* restricted at
  the Qdrant query level at all: instead it's queried with an
  over-fetched candidate limit — `min(candidate_limit * 5, 200)`
  (`ANTHOLOGY_OVERFETCH_FACTOR` / `ANTHOLOGY_OVERFETCH_CAP`,
  `src/retrieval/filtering.py`) — generous enough that even if every one
  of 1934_PM's 10 individually-dated texts ranked in the pipeline's native
  top candidates, the in-range subset after post-filtering would still
  very likely exceed the requested `candidate_limit`. Each returned
  candidate's paragraph_ids are then resolved to an effective year,
  out-of-range ones dropped, and the merged result (settled buckets +
  post-filtered partial bucket) is truncated back down to `candidate_limit`
  before reranking proceeds as normal.

Full implementation, including the exact partitioning logic and the native
`hybrid_search(..., query_filter=...)` plumbing this reuses:
`src/retrieval/filtering.py`. Test coverage (pure-logic unit tests plus
live-corpus integration tests, including the recall-preservation
regression check and the 1902 "L'effort intellectuel" example that
distinguishes `"text"` from `"publication"` mode for the identical query
and range): `tests/test_filtering.py`.

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

## Additive backend surface (added alongside Sprint 8, not part of Sprint 7)

`GET /conversations` (list, newest first), `PATCH /conversations/{id}`
(rename), `DELETE /conversations/{id}` (cascading delete) — Sprint 7 only
shipped lookup-by-id, but the frontend's sidebar conversation list and the
landing page's "last conversation" redirect have no way to enumerate
conversations without it. `Conversation` gained a nullable `title` column
for the rename action. Full frontend context:
[`docs/frontend.md`](frontend.md).

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

`tests/test_filtering.py` (Sprint 11 `work_ids`/`date_range` filtering):
pure-logic unit tests for the eligibility/partitioning/effective-year
functions (no Qdrant needed) plus live-corpus integration tests for
`filtered_hybrid_search` itself — `"publication"` mode's unchanged
behavior, `"text"` mode's distinguishing case (a range covering 1919_ES's
publication year but not "L'effort intellectuel"'s actual 1902 correctly
excludes it under `"text"` mode and includes it under `"publication"`
mode, for the identical query and range), the non-anthology-work
regression check, and the recall-preservation regression test (the
over-fetch/truncate mechanism actually returning the full requested
`top_k`, not fewer). `tests/test_api.py` adds thin endpoint-level plumbing
checks (malformed `date_range` -> 422, filters threaded through to a real
`/retrieve` call) on top of that.
