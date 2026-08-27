import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { IconBook2, IconLoader2, IconMessagePlus, IconPencil, IconTrash } from '@tabler/icons-react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { deriveTitle } from '../lib/title'
import { usePendingConversationsList } from '../state/pendingConversations'
import { Wordmark } from './Wordmark'

export function Sidebar() {
  const navigate = useNavigate()
  const params = useParams()
  const activeConversationId = params.conversationId ? Number(params.conversationId) : null
  const queryClient = useQueryClient()
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')

  const { data } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => api.listConversations(),
  })
  const pendingConversations = usePendingConversationsList()

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: number; title: string }) => api.renameConversation(id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['conversations'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteConversation(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      if (activeConversationId === id) navigate('/new')
    },
  })

  return (
    <aside
      className="flex h-screen w-[200px] shrink-0 flex-col gap-4 p-3"
      style={{ background: 'var(--paper-2)', borderRight: '0.5px solid var(--hairline)' }}
    >
      <div className="px-1 pt-1">
        <Wordmark size={20} />
      </div>

      <button
        type="button"
        onClick={() => navigate('/new')}
        className="flex w-full items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium text-white"
        style={{ background: 'var(--red)' }}
      >
        <IconMessagePlus size={16} />
        Nouvelle conversation
      </button>

      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto">
        {pendingConversations.map((pending) => (
          <button
            key={pending.draftId}
            type="button"
            onClick={() => navigate(`/new/${pending.draftId}`)}
            className="flex items-center gap-2 rounded-md px-2 py-1.5"
            title="Création de la conversation en cours… — cliquer pour la rouvrir"
          >
            <IconLoader2 size={13} className="shrink-0 animate-spin" style={{ color: 'var(--ink-3)' }} />
            <span className="min-w-0 flex-1 truncate text-left text-xs" style={{ color: 'var(--ink-3)' }}>
              {deriveTitle(pending.query)}
            </span>
          </button>
        ))}

        {(data?.conversations ?? []).map((conv) => {
          const title = conv.title ?? (conv.first_query ? deriveTitle(conv.first_query) : 'Nouvelle conversation')
          const isActive = conv.conversation_id === activeConversationId
          const isRenaming = renamingId === conv.conversation_id
          return (
            <div
              key={conv.conversation_id}
              className="group flex items-center gap-1 rounded-md px-2 py-1.5"
              style={{ background: isActive ? 'var(--paper)' : 'transparent' }}
            >
              {isRenaming ? (
                <input
                  autoFocus
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && renameValue.trim()) {
                      renameMutation.mutate({ id: conv.conversation_id, title: renameValue.trim() })
                      setRenamingId(null)
                    }
                    if (e.key === 'Escape') setRenamingId(null)
                  }}
                  onBlur={() => setRenamingId(null)}
                  className="min-w-0 flex-1 rounded border bg-transparent px-1 text-xs"
                  style={{ borderColor: 'var(--hairline)', color: 'var(--ink)' }}
                />
              ) : (
                <button
                  type="button"
                  onClick={() => navigate(`/c/${conv.conversation_id}`)}
                  className="min-w-0 flex-1 truncate text-left text-xs"
                  style={{ color: 'var(--ink)' }}
                  title={title}
                >
                  {title}
                </button>
              )}
              <div className="flex shrink-0 gap-0.5 opacity-0 group-hover:opacity-100">
                <button
                  type="button"
                  aria-label="Renommer"
                  onClick={() => {
                    setRenamingId(conv.conversation_id)
                    setRenameValue(title)
                  }}
                  className="rounded p-1"
                  style={{ color: 'var(--ink-3)' }}
                >
                  <IconPencil size={13} />
                </button>
                <button
                  type="button"
                  aria-label="Supprimer"
                  onClick={() => deleteMutation.mutate(conv.conversation_id)}
                  className="rounded p-1"
                  style={{ color: 'var(--ink-3)' }}
                >
                  <IconTrash size={13} />
                </button>
              </div>
            </div>
          )
        })}
      </nav>

      <button
        type="button"
        onClick={() => navigate('/docs')}
        className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs"
        style={{ color: 'var(--ink-2)' }}
      >
        <IconBook2 size={15} />
        Documentation
      </button>
    </aside>
  )
}
