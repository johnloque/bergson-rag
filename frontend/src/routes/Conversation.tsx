import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { Composer } from '../components/Composer'
import { TurnCard } from '../components/TurnCard'
import { WORK_YEAR_RANGE } from '../lib/works'
import { startOrAttachPendingConversation } from '../state/pendingConversations'
import {
  defaultFilterState,
  toRetrieveFilterParams,
  type RetrieveFilterParams,
} from '../state/retrievalFilter'

interface Draft {
  key: string
  query: string
  /** Snapshotted from the filter control at submit time — each turn keeps
   * its own filter state independent of whatever the control shows later
   * (state/retrievalFilter.ts). */
  filterParams: RetrieveFilterParams
  /** Set once /generate resolves — lets us skip this turn in the persisted
   * list below once it catches up, instead of rendering the same turn
   * twice. */
  turnId?: number
}

export function Conversation() {
  const params = useParams()
  const conversationId = params.conversationId ? Number(params.conversationId) : undefined
  // Present only on /new/:draftId (App.tsx) — a brand-new conversation's
  // first submission, rendered below straight from this param rather than
  // from `drafts` state seeded at mount: react-router reuses this same
  // <Conversation> instance across sibling routes rendering the same
  // component (it doesn't remount just because the matched Route changed),
  // so anything read only once at mount time here would go stale the
  // moment the URL's draftId changes without a fresh mount to notice it.
  const draftId = params.draftId
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [pendingCount, setPendingCount] = useState(0)
  // Sticky across turns in this conversation, not reset on submit — see
  // state/retrievalFilter.ts for why, and FilterControl's active-filter
  // indicator for how that stays visible instead of surprising.
  const [filterState, setFilterState] = useState(() =>
    defaultFilterState(WORK_YEAR_RANGE.min, WORK_YEAR_RANGE.max),
  )

  const { data } = useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: () => api.getConversation(conversationId as number),
    enabled: conversationId !== undefined,
  })

  // A draft keeps rendering itself from its own internal state for the
  // rest of this page's lifetime (useTurnController) — it is never
  // unmounted/replaced here, only appended to. Swapping it for the
  // persisted-list's own <TurnCard turnId=…> once that list catches up
  // would hand the turn to a second, freshly-hydrated controller instance
  // with its own copy of client-only state (chunk include/exclude
  // selection, turnUi.tsx) — any toggle made right around that swap could
  // land on the about-to-be-discarded instance and silently vanish, which
  // is exactly what broke chunk exclusion surviving into Régénérer. So the
  // persisted list instead skips any turn a draft already covers.
  function handleSubmit(query: string) {
    // Snapshotted once, here, at submit time — this turn keeps this filter
    // regardless of any later change to the (sticky) filter control.
    const filterParams = toRetrieveFilterParams(filterState)
    if (conversationId === undefined && !draftId) {
      // Brand-new conversation: register (and start) it under a stable id
      // *before* navigating, so the sidebar's pending placeholder
      // (Sidebar.tsx) and the browser back/forward stack both have
      // somewhere real to point while it's still running, and the
      // /new/:draftId page below always finds it already registered
      // rather than needing anything passed through the navigation itself.
      const newDraftId = crypto.randomUUID()
      startOrAttachPendingConversation(queryClient, newDraftId, query, filterParams)
      navigate(`/new/${newDraftId}`, { replace: true })
      return
    }
    setPendingCount((c) => c + 1)
    setDrafts((d) => [...d, { key: crypto.randomUUID(), query, filterParams }])
  }

  const draftTurnIds = new Set(drafts.map((d) => d.turnId).filter((id) => id !== undefined))
  const persistedTurns = data?.turns.filter((t) => !draftTurnIds.has(t.turn_id)) ?? []
  // Once a first turn already exists, the next submitted query will be the
  // second (or later) in this conversation — the point at which the
  // no-cross-turn-context note near the input becomes relevant.
  const hasPriorTurn = persistedTurns.length + drafts.length >= 1
  const isEmpty = !data?.turns.length && drafts.length === 0 && !draftId

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-8 p-8">
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto pb-4">
        {data?.turns
          .filter((t) => !draftTurnIds.has(t.turn_id))
          .map((t) => <TurnCard key={t.turn_id} turnId={t.turn_id} />)}

        {draftId && (
          <TurnCard
            key={draftId}
            draftId={draftId}
            conversationId={undefined}
            onCreated={(_turnId, newConversationId) => navigate(`/c/${newConversationId}`, { replace: true })}
            // A stale /new/:draftId visit — the submission it pointed to
            // already resolved (and left the pending list) or never
            // existed. Nothing to resume; send the user to a genuinely
            // blank composer instead of an inert page.
            onUnknownDraft={() => navigate('/new', { replace: true })}
          />
        )}

        {drafts.map((draft) => (
          <TurnCard
            key={draft.key}
            pendingQuery={draft.query}
            conversationId={conversationId}
            filterParams={draft.filterParams}
            onCreated={(turnId, newConversationId) => {
              setPendingCount((c) => Math.max(0, c - 1))
              setDrafts((ds) => ds.map((d) => (d.key === draft.key ? { ...d, turnId } : d)))
              if (newConversationId !== conversationId) {
                navigate(`/c/${newConversationId}`, { replace: true })
              }
            }}
          />
        ))}

        {isEmpty && (
          <p className="text-sm" style={{ color: 'var(--ink-3)' }}>
            Posez une première question pour démarrer cette conversation.
          </p>
        )}
      </div>

      <Composer
        onSubmit={handleSubmit}
        disabled={pendingCount > 0 || Boolean(draftId)}
        filterState={filterState}
        onFilterStateChange={setFilterState}
      />

      {hasPriorTurn && (
        <p className="-mt-4 text-xs" style={{ color: 'var(--ink-3)' }}>
          Chaque question est traitée indépendamment, sans mémoire des échanges précédents.
        </p>
      )}
    </div>
  )
}
