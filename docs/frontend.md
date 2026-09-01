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

Test coverage: `lib/retrievalScope.test.ts` (pure logic — the unknown-
filter/null case, the all-8-works default, `work_ids` narrowing, the
`"publication"` vs `"text"` mode distinction for the same range, including
the fixture case from `docs/backend_api.md`'s own Sprint 11 write-up),
`components/TurnCard.consideredSources.test.tsx` (the chevron
appearing/toggling and the rendered list content for the default/
restricted/text-mode cases, both for a live submission and for a
reloaded/hydrated turn), and, backend-side, `tests/test_api.py`'s
`test_retrieve_echoes_and_persists_applied_filter` (the applied filter
round-tripping through `RetrieveResponse` and a subsequent
`GET /turns/{id}`).

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
generation, each as `{work title} ({year}) [{chunk_id}]`
(`lib/generationChunks.ts:computeIncludedChunks`, resolving `work_id`
against the turn's own retrieved-chunk set — always a superset of any one
generation's included chunks, since `/generate` never retrieves beyond
what `/retrieve` already persisted for the turn, `docs/backend_api.md`).
The `[chunk_id]` bracket is a stand-in for a real citation display (work,
title, year, page, paragraph) — `feat/chunk-rail-and-citations`
(`docs/ROADMAP.md`, Sprint 12: "Chunk card shows the real citation... instead
of the raw `chunk_id`") had not landed as of this branch, so this reuses the
same bracketed identifier the generation prompt's citation format and Layer
1's structural check already key on
(`docs/anti_hallucination_guardrails.md`), rather than inventing a second
one. **Follow-up, once that branch lands**: swap `computeIncludedChunks`'s
`[chunk_id]` for the real citation component it introduces.

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
