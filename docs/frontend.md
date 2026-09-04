# Frontend (Sprint 8)

React 19 + Vite + Tailwind v4 + TanStack Query in `frontend/`. Desktop light
mode is the primary deliverable, built exactly to the design consigne (exact
hex tokens, spacing, copy) since no mockup image files exist for this sprint
— the design was approved in a separate conversation and specified in full
in the sprint consigne instead.

Five screens: landing (session-scoped via `sessionStorage`, not
`localStorage` — must reappear on a new tab/session), the sidebar app shell,
the conversation view (query bubble, accumulating processing-steps list,
chunk rail with its pre-generation confidence gauge, collapsed/expanded
answer card with faithfulness highlighting — see the retrieval-confidence
correction in
[`docs/anti_hallucination_guardrails.md`](anti_hallucination_guardrails.md)),
the chunk detail view (`Expliquer`/`Exclure`/`Inclure`), and an in-app
documentation page.

State split three ways: TanStack Query for server reads (`GET /turns/{id}`,
`GET /conversations/{id}`), a small React context
(`frontend/src/state/turnUi.tsx`) for the client-owned included/excluded
chunk set and the accumulated `chunk_judgments` dict (both explicitly
client-side until a `/generate` or `/judge-chunk` call sends them, per this
sprint's spec), and a module-level chunk-text cache
(`frontend/src/state/chunkCache.ts`) working around the backend's own
accepted chunk-text-snapshot limitation (`docs/backend_api.md`) — a turn
whose chunks were never fetched client-side this session (e.g. a cold
reload of an old conversation) falls back to a placeholder rather than
fabricating content.

Verified against the real API (Qdrant + local Ollama judge/generation
models running) as well as 19 component/integration tests (Vitest +
Testing Library, mocked fetch) covering every behavior called out in the
sprint's Tests section — see `frontend/src/**/*.test.tsx`.

## Addendum — multi-turn handling within a conversation, no cross-turn context

Scope decision, not an oversight. Sprint 7b's schema already supports
multiple turns per conversation, but nothing in this project gives a turn
access to prior turns: each query is its own independent retrieve+generate
cycle, with zero memory of earlier turns in the same conversation. This is
deliberate — context threading (e.g. conversation history folded into the
retrieval query or the generation prompt) is a real feature a future sprint
could add, but it isn't planned now, and the UI must not imply it exists.
Consequences, applied to `frontend/`:

- Each turn renders as one visually self-contained unit (query, processing
  steps, chunk rail, answer card), stacked in the conversation view — not as
  continuous chat bubbles, which would imply dialogue memory
  (`components/TurnCard.tsx`, restyled `components/QueryBubble.tsx`).
- Régénérer is scoped strictly to its own turn — it already was,
  structurally: `state/useTurnController.ts` is instantiated once per
  `TurnCard`, and the client-only include/exclude and `chunk_judgments`
  state in `state/turnUi.tsx` is keyed by `turnId`, so there is no shared
  state a regenerate on one turn could read from or write into another.
- From the second query onward in a conversation, a small transparency note
  next to the composer states this explicitly ("Chaque question est
  traitée indépendamment, sans mémoire des échanges précédents.",
  `--ink-3`, `routes/Conversation.tsx`) — the same transparency-over-silence
  principle already applied to the confidence gauge and citation flags in
  Screen 3.

## Addendum — evaluation design documented in-app, and an explicit full-endorsement statement

The in-app "Guide d'utilisation" (`routes/Documentation.tsx`) gained a
"Comment la réponse est vérifiée" section explaining the two independent
post-generation checks from Sprint 6 (structural citation check, per-claim
faithfulness check) plus the retrieval-confidence signal, and how
`should_auto_expand` combines them — written for the end user, not a repeat
of `docs/anti_hallucination_guardrails.md`'s implementation-level detail.

Separately, `AnswerCard.tsx` now states explicitly when every claim the
faithfulness judge extracted was supported by the cited chunks ("Réponse
intégralement confirmée par les passages cités.", green, next to the
existing unsupported-claim highlight note) — previously the UI only ever
surfaced the negative case (a highlighted unsupported passage) and stayed
silent otherwise. This is a narrower exception to `CitationFlag.tsx`'s "no
success state" rule from Screen 3: that rule is about Layer 1 (citation
resolution, still silent on success), not Layer 2 (faithfulness) — the two
are independent checks (`docs/anti_hallucination_guardrails.md`), and only
the latter gained an explicit success state here, on direct request.

## Additive backend surface

Small, additive backend surface added alongside this sprint (not part of
Sprint 7 itself): `GET /conversations`, `PATCH /conversations/{id}`,
`DELETE /conversations/{id}` — needed by the sidebar's conversation list
and the landing page's "last conversation" redirect. Full detail:
[`docs/backend_api.md`](backend_api.md).

## Addendum — retrieval filter UI (Sprint 12, `feat/retrieval-filter-ui`)

Frontend for the `work_ids`/`date_range` `/retrieve` filters shipped
backend-only in Sprint 11 (`feat/retrieval-filtering`,
[`docs/backend_api.md`](backend_api.md)). Lives in the chat bar as an
icon-triggered popover (`components/FilterControl.tsx`, rendered inside
`components/Composer.tsx`) rather than an always-open panel — the common
case is no filtering at all, so the control stays a single unobtrusive
icon (`IconFilter`) until clicked, with a small red dot appearing on it
whenever the current filter state deviates from default
(`state/retrievalFilter.ts:isFilterActive`).

The popover holds three controls:

- **Work checklist** — 8 checkboxes, one per work
  (`src/lib/works.ts:WORKS`, a hand-maintained mirror of `src/works.py`'s
  `WORKS` table — same manual-mirror convention `api/types.ts` already uses
  for `src/api/schemas.py`), all checked by default.
- **Chronological slider** — two range-input handles (start/end year) over
  the corpus's real year span, `src/lib/works.ts:WORK_YEAR_RANGE`, derived
  from `WORKS` rather than hardcoded.
- **Mode toggle** ("Publication"/"Texte") with an inline hint noting it
  only changes results for *L'énergie spirituelle* (1919) and *La Pensée
  et le Mouvant* (1934) — the two anthology works `date_range`'s `"text"`
  mode is meaningful for (`src/lib/works.ts:ANTHOLOGY_WORK_IDS`,
  `docs/backend_api.md`'s Sprint 11 write-up); toggling it has no effect
  on a request for any other work or with no date range set at all.

**Per-turn, not a persisted session filter** (`state/retrievalFilter.ts`):
consistent with the no-cross-turn-context design below, there is nothing
server-side threading a filter across turns — the current filter state is
snapshotted into a plain `{work_ids?, date_range?}` object at the moment a
query is submitted (`routes/Conversation.tsx:handleSubmit`) and carried on
that one `Draft`/turn from then on. The control itself *is* deliberately
sticky in the browser across turns within a conversation (ordinary React
state in `Conversation.tsx`, not reset after each submit) — the
active-filter dot exists specifically so a filter set while composing an
earlier turn is never silently forgotten going into the next one, rather
than to indicate some new backend-persisted concept.

**Default = omit the parameter, not an explicit full-corpus filter**: with
nothing unchecked and the slider never touched, `/retrieve` is called with
neither `work_ids` nor `date_range` present at all — never an explicit
`work_ids` listing all 8 works or a `date_range` spanning the full corpus
— matching `/retrieve`'s own documented "omitted = unfiltered" contract
(`docs/backend_api.md`) exactly, including its one deliberate edge case:
unchecking every work sends an explicit empty `work_ids: []` (a
deliberately-empty allowlist, matches nothing), distinct from never having
touched the checklist at all.

Test coverage: `state/retrievalFilter.test.ts` (pure request-building
logic — default omits both fields, unchecking narrows `work_ids`, the
empty-list edge case, `date_range` with its selected mode once touched),
`components/FilterControl.test.tsx` (checklist/slider/mode-toggle
interactions, the active-filter indicator appearing and disappearing),
and `routes/Conversation.filters.test.tsx` (end-to-end through the real
submission path — the actual `/retrieve` request body for the default,
unchecked-work, and moved-slider cases). The backend's own filtering
behavior is not re-tested here — see `tests/test_filtering.py` for that.

### Expandable "sources considered" detail on the retrieval step

The "Recherche des passages pertinents" `StepLine` (`components/StepLine.tsx`,
now accepts an optional `children` slot behind a collapsed-by-default
chevron) can expand into a bullet list of exactly which works — or, in
`"text"` mode, which individually-dated texts within 1919_ES/1934_PM —
that turn's filter actually left in scope for retrieval: all 8 works when
no filter was applied, the narrowed set when `work_ids` was set, and (in
`"text"` mode) a nested list of the qualifying individual texts under each
affected anthology work. Pure client-side derivation from the turn's own
`filterParams` plus the static `lib/works.ts` mirror
(`lib/retrievalScope.ts:computeConsideredSources`) — no extra API call
needed to compute the list itself.

**Available as soon as the request was sent, not gated on retrieval
completing**: a turn's `work_ids`/`date_range` is known and persisted at
turn creation (`persistence.create_turn`, `src/api/main.py`'s `/retrieve`),
*before* `filtered_hybrid_search` + reranking even run — so `StepLine`
offers the chevron the moment the step starts (spinner still showing), not
only once it's marked done.

**Persisted server-side** (`Turn.work_ids`/`Turn.date_range`,
`src/api/models.py`, both nullable JSON columns, additive-column-migrated
onto an existing dev DB via `src/api/db.py`'s `_sync_additive_columns`) —
survives a reload. `RetrieveResponse` and `TurnDetailResponse` both echo it
back (`docs/backend_api.md`); a reloaded page's `GET /turns/{id})` hydrate
call (`state/useTurnController.ts`) reads it into the same `filterParams`
state a live submission would have set, so the chevron and its list are
identical whether the turn was just submitted this session or the page was
just reloaded. `null` for both fields means "no filter was applied" — the
same contract as an omitted `RetrieveRequest` field, never an explicit
all-8/full-span default — and is what a hydrated *unfiltered* turn shows
(all 8 works), not a "filter unknown" state; that gap (an earlier version
of this feature that only worked for the live session, going silent on
reload) is what this persistence closes. The one residual edge case: a
turn's row created before this persistence existed has no recorded
`work_ids`/`date_range` at all and reads back as `null`/`null` — displayed
as "no filter", which may be wrong for a handful of pre-migration dev-only
rows that actually had one applied via a direct API call before Sprint 12
shipped; accepted, not fixed, since it only affects rows that already
existed before this change landed.

`"text"` mode's individual-text listing is itself a simplification: it
omits the backend's undated-front-matter fallback to the work's own
publication year (`src.works.resolve_paragraph_metadata`, a handful of
paragraphs per anthology at most) — an accepted display-only
approximation (`lib/retrievalScope.ts`), not a second implementation of
`matches_date_range`'s exact paragraph-level logic.

**Follow-up (`feat/chunk-rail-and-citations`): a per-work chevron for the
nested text list.** The qualifying-texts sub-list used to render
unconditionally the moment the outer "sources prises en compte" list was
expanded, with no visible cue that it was there beyond the indentation
itself. `components/ConsideredSourceEntry.tsx` now renders each work's row
with its own small chevron next to the title — shown only when
`entry.texts` is set (i.e. an anthology work under `"text"`-mode filtering
with at least one qualifying text) — collapsed by default, so a user
scanning the outer list gets a clear, explicit affordance for "this work
was narrowed to specific texts, click to see which" rather than a wall of
nested bullets. Non-anthology works and anthology works shown at
whole-work granularity (`"publication"` mode, or no date_range at all)
render no chevron at all, same as before.

Test coverage: `lib/retrievalScope.test.ts` (pure logic — the unknown-
filter/null case, the all-8-works default, `work_ids` narrowing, the
`"publication"` vs `"text"` mode distinction for the same range, including
the fixture case from `docs/backend_api.md`'s own Sprint 11 write-up),
`components/TurnCard.consideredSources.test.tsx` (the outer chevron
appearing/toggling and the rendered list content for the default/
restricted/text-mode cases, both for a live submission and for a
reloaded/hydrated turn; the text-mode case also covers the per-work
chevron collapsing/revealing the nested text list), and, backend-side,
`tests/test_api.py`'s `test_retrieve_echoes_and_persists_applied_filter`
(the applied filter round-tripping through `RetrieveResponse` and a
subsequent `GET /turns/{id}`).

## Addendum — answer display improvements (Sprint 12, `feat/answer-display-improvements`)

Three independent refinements to the answer card and its surrounding
processing-steps checklist, on top of the retrieval filter UI above.

### Included chunks as a collapsible list under "Génération de la réponse"

The "Génération de la réponse" `StepLine` now takes the same optional
`children`/chevron the retrieval step's "sources considered" detail already
uses (`components/StepLine.tsx`) — the exact component and interaction
`feat/retrieval-filter-ui` built, reused as-is rather than a second
disclosure implementation. It was already generic (a plain `children` slot
behind a collapsed-by-default chevron), so no extraction was needed; the
one real gap found reusing it for a second, differently-shaped disclosure
was that its expand/collapse `aria-label` was hardcoded to the retrieval
step's own wording ("Afficher/Masquer les sources prises en compte") —
correct there, misleading here. Fixed with an optional `expandLabel` prop
(defaulting to the original text, so the retrieval step's existing
aria-label and its tests are unchanged) that `components/GenerationBlock.tsx`
overrides with "les passages inclus dans la génération".

Expanding it lists exactly the chunks `entry.chunkIds` names for that
generation, each rendered via `lib/citation.ts:formatCitation`
(`lib/generationChunks.ts:computeIncludedChunks`, resolving `chunk_id`
against the turn's own retrieved-chunk set — always a superset of any one
generation's included chunks, since `/generate` never retrieves beyond
what `/retrieve` already persisted for the turn, `docs/backend_api.md`).
This used to render `{work title} ({year}) [{chunk_id}]` — a stand-in for a
real citation display, since `feat/chunk-rail-and-citations` (below) hadn't
landed as of this addendum. **Retrofitted on `feat/chunk-rail-and-citations`**:
that bracketed-`chunk_id` fallback is gone, replaced by the same shared
`formatCitation` the chunk rail's own cards call — see that section below
for the exact format.

Available as soon as "Générer"/"Régénérer" is clicked, not gated on the
generation finishing — `state/useTurnController.ts`'s `generate()` sets
`chunkIds` on the entry before the `/generate` call even resolves, same
"available before the step completes" rule the retrieval step's own detail
follows.

### Most recent generation shown first

Checked against the real `GET /turns/{id}` response shape rather than
assumed: `persistence.get_turn_generations` (`src/api/persistence.py`)
returns a turn's generations `order_by(Generation.id)` — oldest first, the
same order `state/useTurnController.ts` already stored them in and that its
`generate()` (index-by-`length`, `.at(-1)` for the in-flight check) depends
on. So "most recent first" is a presentation-only reversal in
`components/TurnCard.tsx`, not a change to that state or a client-side
re-sort of the API response.

`TurnCard.tsx` renders only the latest generation as the primary
`GenerationBlock`; older ones are never discarded from the view (this
project has never discarded a generation once made — each is persisted per
Sprint 7b) but sit behind a "N version(s) précédente(s)" chevron toggle,
collapsed by default — the same disclosure convention as the two chevrons
above, scaled to whole generations instead of a bullet list, rather than a
third bespoke interaction. `isFirst` (which drives the
"Génération de la réponse" vs. "Génération d'une nouvelle réponse" label)
stays keyed to true chronological position, independent of display order.

### Markdown rendering for generated answer text

`AnswerCard.tsx` renders `answer` through `react-markdown` (+ `remark-gfm`)
instead of a `whitespace-pre-wrap` plain-text div — a maintained parser, not
hand-rolled, per this project's standing "reuse a fit-for-purpose library"
discipline (`docs/backend_api.md`'s SQLModel rationale makes the same call).

**Faithfulness highlighting had to be re-architected, not just left in
place, to compose with it.** The previous `annotateAnswer` matched a
claim's verbatim quote against the *whole raw answer string* and returned
a flat array of text/`<span>` React nodes — incompatible with markdown
rendering, since react-markdown owns the string-to-tree parsing and a
flagged quote can legitimately fall inside a single markdown text leaf
nested under `<strong>`/`<li>`/etc. Tested explicitly, not assumed to
compose: a naive first attempt (passing the previous transformer function
as if it were a unified plugin attacher) threw immediately in every
markdown render, caught by the new test suite before it shipped.

Fixed by splitting the matching logic from its rendering:

- `lib/highlightMatching.ts` (renamed from `annotateAnswer.tsx`, same
  matching rule, same test coverage translated to its new shape) exports
  `findHighlightRanges(text, claims)` — the pure, quote-matching,
  longest-wins-on-overlap logic, decoupled from any particular tree it's
  applied to.
- `lib/highlightPlugin.ts` exports `rehypeHighlightClaims(claims)`, a
  unified/rehype plugin (`AnswerCard.tsx`'s `rehypePlugins`) that walks the
  *parsed* markdown tree after `remark-gfm` has already structured it into
  elements, and runs `findHighlightRanges` independently on each text leaf
  it finds — wrapping a match in a `<mark>` HAST element nested wherever
  that leaf already was. This is what keeps markdown structure and the
  highlight from fighting each other: a quote inside a bold run or a list
  item is still just text at that leaf, so `<strong>`/`<li>` stay intact
  and `<mark>` nests inside them, rather than the parser stripping an
  injected `<span>` or the highlight cutting across tag boundaries.

`AnswerCard.test.tsx` tests this combination directly (not assumed to
compose cleanly): a flagged quote entirely inside a `**bold**` run, and one
inside a markdown list item — both assert the formatting tag and the
`<mark>` render together, nested correctly, alongside a plain markdown
formatting test (bold/list render as elements, not literal `**`/`-` text).

## Addendum — chunk rail and citations (Sprint 12, `feat/chunk-rail-and-citations`)

Closes out the remaining Sprint 12 chunk-rail items left open by
`feat/retrieval-filter-ui` and `feat/answer-display-improvements` above:
the real per-chunk citation, the rail's default-selection/cap behavior,
and the unified Générer/Régénérer control. Also merges in what would have
been a separate `fix/answer-bullet-citations` branch — that branch hadn't
shipped independently, so its one change (the retrofit above) landed here
instead of as a second PR.

### Shared citation format — `lib/citation.ts`

One function, `formatCitation(chunk: ChunkResult): string`, imported by
both `components/ChunkRail.tsx`/`routes/ChunkDetail.tsx` (the chunk rail
and its detail view) and `lib/generationChunks.ts` (the answer card's
included-chunks bullet list, addendum above) — not two hand-rolled copies
of the same format. Mirrors `src.works.resolve_paragraph_metadata`
(`src/works.py`) at display granularity, the same manual-mirror convention
`lib/works.ts` already uses for `WORKS`/`TEXTS` (no shared build step
between the Python backend and this Vite frontend) — `TEXTS` gained
`paragraphStart`/`paragraphEnd` fields (mirroring
`src.works.TextMetadata`) specifically so this module could reproduce that
resolution client-side.

Three shapes, depending on what the mirrored resolution returns for
`chunk.work_id` + `chunk.paragraph_ids[0]`:

- Non-anthology work: `"{work_title} ({work_year}), paragraphe {n}"`.
- Anthology work (1919_ES/1934_PM) resolving to a specific
  individually-dated text: `"{work_title} ({work_year}) — {text_title}
  ({text_year}), paragraphe {n}"`.
- Anthology work chunk falling back to work-level only (front matter, no
  covering individually-dated text): same as the non-anthology format — no
  empty/null text-level fields leak into the string.

`chunk.paragraph_ids[0]` is used directly, not a min-max range over every
element: checked against `src/ingestion/chunking.py` rather than assumed
— one chunk = one paragraph in this project's chunking scheme, so
`paragraph_ids` always has exactly one element in the real corpus, the
same "index 0 is representative of the whole chunk" convention
`src/generation/prompt.py` already relies on for this field. No
`"paragraphes {n}-{m}"` range formatting is implemented, since no chunk
can currently span more than one paragraph to need it — revisit if the
chunking scheme ever changes.

Test coverage: `lib/citation.test.ts` (all three format shapes, plus the
empty-`paragraph_ids` and unknown-`work_id` edge cases, against the shared
function directly) and `components/citationConsistency.test.tsx` (a direct
equality assertion between the chunk rail's rendered citation and the
answer bullet list's rendered citation for the same chunk — not two
independent "looks reasonable" checks).

### Chunk rail: 15 chunks, top 3 included by default, 5-chunk cap

Checked against the real `/retrieve` response rather than assumed: the
rail shows the top 15 post-reranking chunks
(`src.retrieval.reranking.DEFAULT_RERANK_CANDIDATES = 15`), but
`RetrieveRequest.top_k` (`src/api/schemas.py`) defaults to 3 and
`/retrieve`'s response is always exactly `top_k` chunks
(`reranked[: body.top_k]`, `src/api/main.py`) — so the frontend, which
previously omitted `top_k` entirely, only ever saw 3 chunks. Fixed by
requesting `top_k: CHUNK_RAIL_TOP_K` (`lib/retrievalConfig.ts`, `= 15`)
explicitly from both `/retrieve` call sites
(`state/useTurnController.ts`'s `runNewTurn`,
`state/pendingConversations.ts`'s `startOrAttachPendingConversation`).
This doesn't reopen `DEFAULT_TOP_K`'s own context-window rationale (that
default was lowered from 10 to 3 specifically so `/generate`/`/evaluate`
don't overflow the judge's context window, `src/api/schemas.py`): those
two calls only ever see the client-curated `included` subset
(state/turnUi.tsx), itself capped at 5 below — retrieval breadth and
generation-input size are decoupled by the rail's own selection mechanism.

Default selection changed from "every retrieved chunk included" to the
top `DEFAULT_INCLUDED_COUNT = 3` (by rank — `state/turnUi.tsx`'s `init`
reducer case defaults the first 3 ids in the array it's given, always the
turn's reranked order, to included and the rest to explicitly excluded),
with `MAX_INCLUDED_CHUNKS = 5` selectable at once. **A 6th selection is
blocked, not auto-uncheck-least-recently-checked**: the `toggle` reducer
case is a true no-op once 5 are already included — chosen over the
auto-uncheck alternative because a silent substitution (excluding a chunk
the user never touched) seemed more surprising than a click that visibly
does nothing. The reducer is the single source of truth for this, since
two separate UI surfaces can toggle the same turn's inclusion state
(`components/ChunkRail.tsx` and `routes/ChunkDetail.tsx`'s own
Inclure/Exclure button) — the cap has to hold regardless of which one
changed it. Both surfaces also disable their own "Inclure" affordance
(with a tooltip) once the cap is reached and show a running
`{n}/5 passages sélectionnés` count, so the block is never a silent no-op
from the user's point of view.

Test coverage: `components/ChunkRail.test.tsx` (exactly 3 of 15 included
by default in rank order, selecting up to 5, the disabled/no-op 6th
selection, and that excluding a chunk frees a slot back up).

### Chunk cards show the real citation

`components/ChunkRail.tsx`'s cards and `routes/ChunkDetail.tsx`'s header
now render `formatCitation(chunk)` in place of the bare `work_id` they
showed before (the rail never actually rendered the raw `chunk_id` itself,
contrary to how `docs/ROADMAP.md`'s Sprint 12 entry phrased it — but the
effect is the same: a real citation instead of an internal identifier).

### Générer/Régénérer: one control, to the right of the rail

`components/TurnCard.tsx` wraps `ChunkRail` and the existing
Générer/Régénérer `<button>` in one flex row (`data-testid="chunk-rail-row"`)
instead of stacking the button below the rail — the rail keeps its own
horizontal scroll (`min-w-0` on its wrapper lets it shrink in the flex
row rather than pushing the button off-screen) while the button sits in a
fixed-width column beside it. Placement only: the click handler is still
`state/useTurnController.ts`'s `generate()`, same request, same in-flight
guard, same append-a-new-`GenerationEntry` behavior as the Sprint 10
manual-generation trigger this unifies with the regeneration action —
already covered by `components/TurnCard.generations.test.tsx` and
`components/TurnCard.integration.test.tsx`'s existing Générer/Régénérer
assertions, which needed no changes to keep passing.

## Addendum — chunk neighbor expansion (Sprint 12, `feat/chunk-neighbor-expansion`)

Restructures Screen 4 (chunk inspection) into a master-detail view, and
extends Screen 3's rail to surface chunks included via that exploration.
Builds on `feat/chunk-rail-and-citations`'s citation format and rail
defaults above, and on the new backend endpoint
`GET /chunks/{chunk_id}/neighbors` — full endpoint semantics, including the
section-boundary rule and the known 1-paragraph-per-chunk simplification, in
[`docs/backend_api.md`](backend_api.md).

### Screen 4: master-detail, not one chunk per route

`routes/ChunkDetail.tsx` still lives at the same route
(`/c/:conversationId/turn/:turnId/chunk/:chunkId`), but the `:chunkId`
param now only ever seeds the *initial* focus, once, on mount — it no longer
drives the page on every click. Three stacked zones, all reading/writing one
local `focusedChunk` piece of state (`lib/focusedChunk.ts`'s `FocusedChunk`,
one shape for both a real `ChunkResult` and a neighbor-resolved
`ChunkNeighborSummary`, so the detail panel doesn't have to branch on which
produced it):

1. **Retrieval rail, pinned** — `components/ChunkRail.tsx`, reused exactly
   as Screen 3 uses it (same cards, same include/exclude toggle, same x/5
   counter). The only change needed was an optional `onInspect` prop:
   Screen 3 leaves it unset (its "Inspecter" button keeps navigating to
   Screen 4, unchanged); Screen 4 passes `setFocusedChunk`, so a click
   updates local state instead of navigating — this is what removes the old
   per-chunk-route back-button/re-inspect friction.
2. **Position filmstrip** — `components/PositionFilmstrip.tsx`. Fetches
   `GET /chunks/{focusedChunk.chunk_id}/neighbors` (TanStack Query, keyed on
   the focused chunk_id — refetches and the filmstrip re-centers whenever
   focus changes) and renders three cells (previous / current / next)
   joined by arrow icons. Deliberately styled to read as a different
   concept from the rail above — dashed border, `--paper-2` background, vs.
   the rail's solid-bordered cards on plain paper — and, unlike the rail's
   cards (which do show a 2-line text preview), a filmstrip cell shows only
   a compact citation, never any chunk text at all: neither selector is
   where full text renders, only the shared detail panel below is. A `null`
   neighbor (section boundary, or simply the start/end of the work) still
   renders its own disabled, empty cell ("Début de section"/"Fin de
   section") rather than being omitted — so the user sees there's no further
   neighbor in that direction instead of wondering why a cell is missing.
   Clicking a resolved cell sets that chunk as focused directly (the
   response already carries its full text — no second fetch needed).
3. **Detail panel** — the one place full text, the real citation
   (`lib/citation.ts:formatCitation`, loosened to a minimal `CitableChunk`
   shape so it accepts both `ChunkResult` and `ChunkNeighborSummary` without
   a conversion step), score (subdued, omitted entirely for a neighbor-origin
   chunk — it was never retrieved/ranked, so there's nothing to show),
   "Expliquer" (`judge_chunk`), and "Inclure"/"Exclure" render, for whichever
   chunk is currently focused regardless of which selector set it.

   **Origin tag**: "Depuis la recherche" / "Voisin — hors des résultats de
   recherche" (`data-testid="chunk-origin-tag"`), derived from
   `turnUi.isRetrieved(turnId, chunk_id)` — i.e. whether this chunk_id is
   genuinely one of the turn's originally-retrieved candidates, not which
   selector was last clicked. The two can diverge: a filmstrip neighbor can
   turn out to already be one of the retrieved 15, in which case it's
   tagged "Depuis la recherche" even though the filmstrip is what surfaced
   it this time — the tag is about the chunk's real relationship to the
   search results, matching its own wording ("hors des résultats de
   recherche"), not a breadcrumb of the click that led here.

   A direct visit/reload of this route calls `turnUi.initTurn` itself once
   `GET /turns/{id}` resolves (mirroring `state/useTurnController.ts`'s own
   hydrate effect) — needed since this route doesn't go through that hook,
   and both `isRetrieved` and the inclusion cap depend on `retrievedIds`
   having been seeded. One accepted gap: a reload landing directly on a
   neighbor-origin `:chunkId` that was never included has nowhere to
   recover its content from (turnUi's neighbor map is client-only,
   Sprint 8's addendum, and there's no generic get-chunk-by-id endpoint) —
   the panel falls back to a loading placeholder, same "accept, don't
   fabricate" discipline as the existing chunk-text-snapshot limitation.

### Screen 3: the rail represents the FULL set sent to generation

`state/turnUi.tsx` gained a `neighbors: Record<turnId, Record<chunkId,
ChunkNeighborSummary>>` map alongside its existing `included` map — the
single shared source of truth both `components/ChunkRail.tsx` and
`routes/ChunkDetail.tsx` read and write, so Screen 3 and Screen 4 always
agree on what's included for a turn without either screen reimplementing
the other's state. A chunk's presence in this map *is* its inclusion state
(there is no "present but excluded" entry, unlike the rail-origin
`included` map) — `toggleNeighborChunk` adds it (subject to the same
combined `MAX_INCLUDED_CHUNKS` cap the rail-origin `toggleChunk` already
enforced, via a shared `includedCountFor` helper) or removes it entirely, a
true toggle. A second `retrievedIds: Record<turnId, string[]>` map (set once
at `initTurn`) is what lets the reducer/components tell a rail-origin
chunk_id from a neighbor-origin one — the same check the origin tag above
uses.

`components/ChunkRail.tsx` renders `turnUi.getNeighborChunks(turnId)` in a
**second, separately-titled rail row** below the retrieved-candidates rail
(`data-testid="neighbor-rail"`, titled "Chunks voisins ajoutés
manuellement" — the retrieved rail above is titled "Chunks issus de la
recherche") — a refinement over the original single-rail-plus-divider
layout, so a card added via Screen 4's neighbor exploration is visible
without having to scroll the first rail out from under it. Each rail
scrolls independently. Neighbor-origin cards:

- Are always shown as included (existence in the map = included) with a
  **dashed** red border, vs. rail-origin cards' solid red border when
  included — reusing the filmstrip's own dashed-vs-solid vocabulary rather
  than inventing a third visual style.
- Show the real citation (`formatCitation`, work + paragraph — never a
  rank-based position, since a neighbor was never ranked) and a small arrow
  icon (`IconArrowsExchange`) marking neighbor origin. **No distance
  badge** here (QA correction after an earlier version added one, `lib/
  chunkOffset.ts`'s `distanceFromNearestAnchor`): this rail has no reliable
  way to know which originally-retrieved chunk a given neighbor was
  actually expanded from — the nearest one by paragraph distance isn't
  necessarily the one the user navigated from — so a "+1"/"-2" badge here
  would look precise while sometimes being wrong. `PositionFilmstrip`'s
  previous/current/next cells (`data-testid="filmstrip-cell-{role}-offset"`)
  keep their own badge: those three are always exactly ±1 from whichever
  chunk is currently focused (derived from the *current* cell's own offset,
  not independently recomputed per cell — an earlier version that did
  recompute independently could show "0" on two adjacent cells when the
  previous/next chunk happened to also be a retrieved anchor), so there's
  no such ambiguity for them.
- Their "Exclure" click calls `toggleNeighborChunk`, which **removes the
  card from the rail entirely** — not a greyed-out permanently-excluded
  card the way excluding a rail-origin (actually-retrieved) chunk stays
  visible. A neighbor chunk was manually opted into inclusion; opting out
  undoes that addition instead of leaving a ghost entry for something that
  was never part of the retrieved set.

The shared `x/5` counter (`turnUi.getIncludedCount`) and cap apply
uniformly regardless of origin — a neighbor-included chunk counts the same
as a rail-origin one, computed once (`includedCountFor`) and read by both
`toggleChunk`'s and `toggleNeighborChunk`'s cap checks.

`state/useTurnController.ts`'s `generate()` folds `turnUi.getNeighborChunks`
into both the `chunk_ids` sent for the in-flight `GenerationEntry` and the
`/generate` request body itself (`lib/chunkInput.ts:neighborSummaryToChunkInput`,
same shape as `toChunkInput` but with `score: null`). `components/TurnCard.tsx`
also passes the turn's neighbor chunks alongside its retrieved ones into
`GenerationBlock`'s citation lookup (`lib/generationChunks.ts`, its `chunks`
param loosened the same way `formatCitation`'s was) — otherwise a
generation that included a neighbor-origin chunk would show "Œuvre
inconnue" for it in the included-chunks disclosure.

Test coverage: `state/turnUi.test.tsx` (the neighbor map's toggle-on/toggle-
off-removes-entirely behavior, the shared cap combining rail- and
neighbor-origin counts, `isRetrieved`, per-turn isolation);
`components/ChunkRail.neighbors.test.tsx` (the second titled rail, its
shared counter, exclude-removes-entirely behavior, and the absence of any
distance badge); `components/PositionFilmstrip.test.tsx` (cell rendering
from a real neighbors response, each cell's distance badge — including the
regression case where the previous/next chunk is itself a retrieved
anchor — the disabled/empty null-neighbor cell, click-to-select,
refetch-on-focus-change);
`routes/ChunkDetail.test.tsx` (initial URL-driven
focus and its origin tag, a rail-card click and a filmstrip-cell click both
updating the same detail panel with matching origin tags, and — sharing one
`TurnUiProvider` between a `ChunkDetail` and a standalone `ChunkRail`
instance, the same setup `App.tsx` gives the real app — including a
neighbor chunk from the detail panel appearing in the rail with the dashed
border and real citation).

## Addendum — Presentation screen and sidebar restructure (Sprint 12, `feat/sidebar-restructure`)

Adds a Presentation screen and restructures the sidebar. Builds on the
chunk-neighbor-expansion addendum above.

Revised after the initial cut: Presentation started as a third
full-screen pre-app step between Landing and the app (its own centered
layout, an "Entrer dans l'application" button resolving
`lastConversationPath()`). It's now a normal sidebar destination nested
under `AppShell`, alongside Guide d'utilisation and Sources — Landing's
"Commencer" and the sidebar icon both still target `/presentation`, but
landing there means being in the app already (sidebar and all), not a
separate screen to exit from.

### Entry flow

- **Landing** (`routes/Landing.tsx`) — unchanged: session-scoped auto-show
  via `sessionStorage` (`lib/session.ts`), shown once per session, never
  reachable by manual navigation from within the app. Its "Commencer"
  button navigates to `/presentation`.
- **Presentation** (`routes/Presentation.tsx`, `/presentation`) — nested
  under `AppShell` like the conversation and guide routes, so it renders
  with the full sidebar. Reached from Landing's "Commencer", and from
  clicking the wordmark/icon at any later point (`components/
  Sidebar.tsx`) — that icon always targets `/presentation`, since Landing
  is never a valid manual destination. Content is just README's "What it
  does" paragraph, near-verbatim in French, styled like Guide
  d'utilisation and Sources — no button, no separate "enter the app"
  step.
- **The app** — for a *returning* session, Landing's auto-skip resolves
  `lastConversationPath()` (`lib/entry.ts`) directly, bypassing both
  Landing and Presentation. A first-time session goes through Landing →
  Presentation and from there uses the sidebar (new conversation or an
  existing one) like any other in-app navigation.

### Sidebar (`components/Sidebar.tsx`)

- Wordmark/icon at top, a button targeting `/presentation` (see above) —
  the app's default landing spot once inside.
- Resizable via a drag handle on the right edge (`data-testid=
  "sidebar-resize-handle"`), bounded to 180–360px, width persisted to
  `localStorage` (`bergson_sidebar_width`) on every drag and restored on
  mount — a per-browser layout preference, not synced server-side.
- Two independently collapsible sections, each with its own open/closed
  `useState` (`SectionHeader`, local to `Sidebar.tsx`):
  - **"Guide & Sources"** — three sub-page links: `routes/
    Presentation.tsx` (`/presentation`), `routes/GuideUtilisation.tsx`
    (`/guide/utilisation`) and `routes/Sources.tsx` (`/guide/sources`),
    all nested under `AppShell` like the conversation routes. Replaces
    the old single `/docs` route and its `Documentation.tsx`, which had
    drifted out of date (no mention of neighbor exploration, for
    instance).
  - **"Conversations"** — the conversation list (pending-conversation
    reattachment, rename/delete affordances), unchanged.
  - The **"Nouvelle conversation"** button sits between these two
    sections, at the same level as their headers rather than inside
    either — always visible regardless of which section is expanded or
    collapsed.
- **"Réglages"**, pinned below the scrollable Conversations section (last
  flex child, not part of the `overflow-y-auto` area) — always visible,
  itself click-to-expand/collapse like the two sections above, but
  content-free: expanding it shows only "Aucun réglage disponible pour le
  moment." Functional settings (`top_k_retrieval`, prompts, LLM choice)
  are `feat/settings-panel`, a separate branch.

### Placeholder content

- **Presentation**: README's "What it does" paragraph (see above).
- **Sources** (`routes/Sources.tsx`): short paragraph — the corpus's
  public-domain status in France (70-years-post-mortem rule, from
  README's License section) and bergson-synoptique's role as the source
  of the paragraph-level XML encoding and reference editions (`docs/
  ROADMAP.md`'s "Source data" decision).
- **Guide d'utilisation** (`routes/GuideUtilisation.tsx`): short
  walkthrough of the actual current flow — retrieve (top 15, top 3
  pre-selected) → inspect chunks (read, explain, include/exclude up to 5,
  explore neighbors) → generate → blurred-until-verified answer (citation
  check, then faithfulness check) → optionally adjust selection and
  regenerate. Deliberately short, not a restatement of the old
  `Documentation.tsx`'s longer "Comment la réponse est vérifiée" section.

Test coverage: `routes/Landing.test.tsx` (auto-show regression, "Commencer"
→ Presentation), `routes/Presentation.test.tsx` (renders as plain content,
no leftover entry button), `components/Sidebar.test.tsx` (wordmark →
Presentation never Landing, resize persisting across a remount, the three
collapsible entries — including Présentation — toggling independently,
conversation-list navigation unchanged) and the existing `components/
Sidebar.pendingConversation.test.tsx`, updated to navigate via the
"Guide d'utilisation" sidebar link instead of the removed "Documentation"
one.

## Known gap, not a finished feature: dark mode and full responsive layout

The design tokens are CSS custom properties (`frontend/src/index.css`), not
hardcoded Tailwind colors, specifically so a dark-mode pass is a
values-swap later rather than a rewrite — but no dark-mode values are
defined yet, since that design pass hasn't happened. Likewise, only the
sidebar/chunk-rail breakpoints that were straightforward with Tailwind's
responsive utilities are in place; the layout has not been comprehensively
designed or tested for mobile/tablet widths. Both remain explicitly open,
to be picked up in a later, dedicated design pass rather than assumed
complete from this sprint.
