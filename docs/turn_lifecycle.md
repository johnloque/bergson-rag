# Turn lifecycle and manual generation (Sprint 10, `fix/turn-lifecycle-and-manual-generation`)

Two independent bugs and one deliberate product reversal, all resolved by
moving turn creation from `/generate` to `/retrieve` and removing automatic
generation. Diagnosed before fixing, per this project's standing discipline
(see `docs/ROADMAP.md`'s Sprint 10 note).

## 1. Turn creation moves to `/retrieve`

**Before this branch**: `/retrieve` (`src/api/main.py`) was stateless —
hybrid search + reranking, no persistence. `/generate` (`src/api/persistence.py`'s
old `resolve_turn`) created the turn (and conversation, if absent) as a side
effect of its own call, and only the turn's *initial* `/generate` call
persisted the retrieved chunk set (`save_retrieved_chunks`), guarded by an
`if body.turn_id is None` check.

**After**: `POST /retrieve` (`RetrieveRequest.conversation_id`,
`RetrieveResponse.turn_id`/`conversation_id`) creates the turn — and a new
conversation, if `conversation_id` is absent — immediately, and persists the
retrieved chunk set against it in the same request, before any generation
happens. The conversation/turn creation check (`persistence.create_turn`)
runs *before* the retrieval call itself, so an unknown `conversation_id`
404s without paying for hybrid search + reranking first.

`POST /generate` (`GenerateRequest.turn_id`, now required) no longer creates
turns at all, whether this is the turn's first, manually-triggered
generation or a later regeneration — it 404s on an unknown `turn_id`
(`persistence.get_turn_or_404`) exactly like a regeneration always did.
`query` is no longer resent in the request either: `/generate` reads it back
from the persisted turn (`turn.query`) instead, the same "server-side value,
not a client-resubmitted one" trust boundary Sprint 7b already applied to
`/evaluate`'s `(query, chunks, answer)`. `/generate` also no longer touches
`retrieved_chunks` at all — that table has exactly one writer now
(`/retrieve`), removing the "only the initial call persists it" conditional
entirely.

This is the root fix for two of this sprint's three problems, not just a
prerequisite for the manual-generation UI change below.

## 2. Manual generation reverses the Sprint 5/6 default, on purpose

Sprint 5/6 established always-automatic generation (retrieval immediately
followed by generation, no button, no blocking) as a core product principle
(`docs/anti_hallucination_guardrails.md`). Direct user feedback overturned
this specifically for this audience: researchers using this tool want to
review the retrieved chunks — excluding weak ones, inspecting/explaining a
chunk (`Expliquer`) — *before* committing to a generation call, not after.

`should_auto_expand` and the collapsed-by-default answer card are
**unchanged** by this reversal: they still govern what happens to the
display once generation completes (`src/generation/guardrail.py`). Only the
*trigger for starting* generation changes — an explicit click, not automatic
on question submit.

Frontend (`frontend/src/state/useTurnController.ts`): `runNewTurn` now calls
only `/retrieve`; it no longer calls `/generate` at all. A single manually
triggered function (`generate`) fires on both a turn's very first generation
and every subsequent regeneration — same request shape (`turn_id`, the
turnUi-included chunk subset, accumulated `chunk_judgments`), same in-flight
guard, same "append a new `GenerationEntry`" behavior. This reuses the
existing regenerate control/logic rather than building a second, separate
"first generation" path, per the Sprint 10 plan. `TurnCard.tsx` renders one
button, labelled "Générer" before any generation exists and "Régénérer"
after, directly under the chunk rail — a functional placement only; Sprint
12 owns the final visual design (a single control to the right of the chunk
rail).

Because `turn_id`/`conversation_id` are now known as soon as `/retrieve`
resolves, the `/new -> /c/{id}` redirect (`onCreated`) also moved earlier —
it used to fire only once `/generate` resolved. This turned out to matter
for bug 4 below, not just for correctness of the turn-lifecycle move itself.

## 3. `/new` "nouvelle conversation" button inactive — diagnosis and fix

**Diagnosed as (a)**: a router no-op, not stale client state left over from
the old turn-creation timing. `Sidebar.tsx`'s button calls
`navigate('/new')` unconditionally. react-router does not remount a route's
element just because `navigate()` was called to the path it's already
showing — clicking "Nouvelle conversation" while already on `/new` changed
nothing about which component instance was mounted, so `Conversation.tsx`'s
own `drafts`/`pendingCount` state (`routes/Conversation.tsx`) survived
untouched instead of starting a genuinely fresh turn.

Moving turn creation to `/retrieve` does **not** resolve this as a side
effect — verified explicitly (per this sprint's own discipline) rather than
assumed, with a regression test (`frontend/src/App.newConversation.test.tsx`)
exercising the exact reported scenario: submit a query, then click "Nouvelle
conversation" again before `/retrieve` even resolves, still nominally on
`/new`. It fails without a dedicated fix.

**Fix**: `App.tsx`'s `/new` route element is keyed on `location.key`
(`<Conversation key={location.key} />`), inside a small `AppRoutes`
component that reads `useLocation()` once per render. `location.key`
changes on every `navigate()` call regardless of whether the path changed,
so keying on it forces a real remount every time — discarding any in-flight
draft state instead of leaving it to survive a no-op navigation.

## 4. "Vérifié" status lost on navigation — diagnosis and fix

**Diagnosed as: not (a), not (b) in isolation — the derivation logic itself
is correct.** `useTurnController.ts`'s hydrate effect does call
`GET /turns/{id}` on every mount with a `turnId` prop, and `AnswerCard.tsx`'s
`expanded = revealed || evaluation?.should_auto_expand === true` correctly
recovers the auto-expand state from a hydrated `evaluation` — this was
confirmed with an isolated component test mounting `<TurnCard turnId={...}>`
fresh against a mocked `GET /turns/{id}` response, for both
`should_auto_expand: true` (renders unblurred) and `should_auto_expand:
false` with a completed evaluation (renders the "Vérifié" badge, collapsed).
Both passed against the pre-existing code, unmodified.

**Real cause (c), shared with bug 1's root cause**: under the old
always-automatic-generation flow, the `/new -> /c/{id}` redirect fired only
once `/generate` resolved — i.e. at almost exactly the moment the fresh
answer first appeared and evaluation state was still unresolved. That forced
a full remount of `Conversation`/`TurnCard` right as an in-flight
`/generate`-then-later-`/evaluate` sequence was in progress, discarding the
component that had initiated those calls out from under itself. The
manual-generation reversal (bug 2) removes the automatic call entirely, and
moving turn creation to `/retrieve` (bug 1) moves the redirect to fire right
after retrieval — well before generation or evaluation ever starts. By the
time a user triggers "Générer" and later "Évaluer", they are already on the
stable, hydrated `/c/{id}` route; no further redirect-driven remount can
land mid-flight of either call.

This is fixed as a side effect of bugs 1 and 2 together, not by a separate
UI patch — confirmed with a dedicated regression test (added to
`frontend/src/components/TurnCard.integration.test.tsx`): a full retrieve ->
manual generate -> evaluate cycle (`should_auto_expand: true`), then a
simulated navigate-away-and-back (unmount, then mount a fresh `<TurnCard
turnId=...>` hydrating purely from `GET /turns/{id}`) — the answer stays
unblurred with no "Lire quand même" prompt, matching the live pre-navigation
state exactly.

## Test coverage

- `tests/test_api.py`: `/retrieve` now persists the turn and its retrieved
  chunks (`test_retrieve_persists_turn_and_retrieved_chunks`), a second
  `/retrieve` call with `conversation_id` reuses the conversation
  (`test_retrieve_second_call_with_conversation_id_reuses_conversation`), an
  unknown `conversation_id` 404s
  (`test_retrieve_unknown_conversation_id_returns_404`) before retrieval
  even runs. Every `/generate` test updated to require an existing
  `turn_id`, created directly (`_create_turn`, standing in for a prior
  `/retrieve` call) rather than letting `/generate` create one.
- `tests/test_persistence.py`: `_create_turn` extended with optional
  `conversation_id`/`retrieved_chunks` parameters so tests can seed exactly
  what a real `/retrieve` call would have persisted, without needing a live
  one. `test_regenerate_with_excluded_chunk_keeps_it_in_retrieved_chunks`
  re-targeted at the new invariant: `/generate` never writes to
  `retrieved_chunks` at all any more (that table has exactly one writer,
  `/retrieve`), not just "the initial call is the only writer".
  `test_get_conversation_lists_its_turns` no longer needs Qdrant or an LLM at
  all, now that turn creation doesn't require exercising `/generate`.
- `frontend/src/components/TurnCard.integration.test.tsx`: rewritten for the
  no-auto-generate flow (a new test asserts `/generate` is never called
  after `/retrieve` alone), the unified Générer/Régénérer control, and the
  navigate-away-and-back regression above.
- `frontend/src/routes/Conversation.test.tsx`: the draft/persisted-instance
  chunk-exclusion race now exercises the `/retrieve`-triggered redirect
  instead of the old `/generate`-triggered one.
- `frontend/src/App.newConversation.test.tsx` (new): the `/new` inactive-
  button regression test described above.
- Sprint 6 guardrail fixtures (`tests/test_guardrail.py`'s Q001/Q004/Q008/
  Q009/Q002) are untouched by this branch — `src/generation/guardrail.py`,
  `signals.py`, and `generate.py` were not modified, only `src/api/`, so
  there is no code path by which this branch could regress them.
