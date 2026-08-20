import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { Composer } from '../components/Composer'
import { TurnCard } from '../components/TurnCard'

interface Draft {
  key: string
  query: string
  /** Set once /generate resolves — lets us skip this turn in the persisted
   * list below once it catches up, instead of rendering the same turn
   * twice. */
  turnId?: number
}

export function Conversation() {
  const params = useParams()
  const conversationId = params.conversationId ? Number(params.conversationId) : undefined
  const navigate = useNavigate()
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [pendingCount, setPendingCount] = useState(0)

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
    setPendingCount((c) => c + 1)
    setDrafts((d) => [...d, { key: crypto.randomUUID(), query }])
  }

  const draftTurnIds = new Set(drafts.map((d) => d.turnId).filter((id) => id !== undefined))

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-8 p-8">
      <div className="flex flex-1 flex-col gap-10 overflow-y-auto pb-4">
        {data?.turns
          .filter((t) => !draftTurnIds.has(t.turn_id))
          .map((t) => <TurnCard key={t.turn_id} turnId={t.turn_id} />)}

        {drafts.map((draft) => (
          <TurnCard
            key={draft.key}
            pendingQuery={draft.query}
            conversationId={conversationId}
            onCreated={(turnId, newConversationId) => {
              setPendingCount((c) => Math.max(0, c - 1))
              setDrafts((ds) => ds.map((d) => (d.key === draft.key ? { ...d, turnId } : d)))
              if (newConversationId !== conversationId) {
                navigate(`/c/${newConversationId}`, { replace: true })
              }
            }}
          />
        ))}

        {!data?.turns.length && drafts.length === 0 && (
          <p className="text-sm" style={{ color: 'var(--ink-3)' }}>
            Posez une première question pour démarrer cette conversation.
          </p>
        )}
      </div>

      <Composer onSubmit={handleSubmit} disabled={pendingCount > 0} />
    </div>
  )
}
