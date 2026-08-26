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
