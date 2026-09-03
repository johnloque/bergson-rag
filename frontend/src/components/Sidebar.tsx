import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  IconChevronDown,
  IconChevronRight,
  IconLoader2,
  IconMessagePlus,
  IconPencil,
  IconSettings,
  IconTrash,
} from '@tabler/icons-react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { deriveTitle } from '../lib/title'
import { usePendingConversationsList } from '../state/pendingConversations'
import { Wordmark } from './Wordmark'

const WIDTH_KEY = 'bergson_sidebar_width'
const MIN_WIDTH = 180
const MAX_WIDTH = 360
const DEFAULT_WIDTH = 220

function readStoredWidth(): number {
  const raw = Number(localStorage.getItem(WIDTH_KEY))
  if (Number.isFinite(raw) && raw >= MIN_WIDTH && raw <= MAX_WIDTH) return raw
  return DEFAULT_WIDTH
}

interface SectionHeaderProps {
  icon?: ReactNode
  title: string
  open: boolean
  onToggle: () => void
}

function SectionHeader({ icon, title, open, onToggle }: SectionHeaderProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium"
      style={{ color: 'var(--ink-2)' }}
    >
      {icon}
      <span className="flex-1 text-left">{title}</span>
      {open ? <IconChevronDown size={13} /> : <IconChevronRight size={13} />}
    </button>
  )
}

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const params = useParams()
  const activeConversationId = params.conversationId ? Number(params.conversationId) : null
  const queryClient = useQueryClient()
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [width, setWidth] = useState(readStoredWidth)
  const [guideOpen, setGuideOpen] = useState(true)
  const [conversationsOpen, setConversationsOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const resizing = useRef(false)

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

  // Resizable, bounded, persisted (localStorage — a per-browser layout
  // preference, not app state worth syncing server-side). Registered once
  // (empty deps): handleMove reads only the live pointer position, so
  // there is no stale-closure reason to re-subscribe on every width change.
  useEffect(() => {
    function handleMove(e: MouseEvent) {
      if (!resizing.current) return
      const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, e.clientX))
      setWidth(next)
      localStorage.setItem(WIDTH_KEY, String(next))
    }
    function handleUp() {
      resizing.current = false
    }
    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
    return () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
    }
  }, [])

  return (
    <aside
      className="relative flex h-screen shrink-0 flex-col gap-3 p-3"
      style={{ width, background: 'var(--paper-2)', borderRight: '0.5px solid var(--hairline)' }}
    >
      {/* Reached only via the automatic per-session show
          (routes/Landing.tsx) — from inside the app, this icon always goes
          to the Presentation screen instead (docs/frontend.md). */}
      <button
        type="button"
        onClick={() => navigate('/presentation')}
        className="w-fit rounded px-1 pt-1 text-left"
        aria-label="Présentation de Bergson-RAG"
      >
        <Wordmark size={20} />
      </button>

      <div className="flex flex-col gap-0.5">
        <SectionHeader
          title="Guide & Sources"
          open={guideOpen}
          onToggle={() => setGuideOpen((o) => !o)}
        />
        {guideOpen && (
          <div className="flex flex-col gap-0.5 pl-[19px]">
            <button
              type="button"
              onClick={() => navigate('/guide/utilisation')}
              className="rounded-md px-2 py-1.5 text-left text-xs"
              style={{ color: location.pathname === '/guide/utilisation' ? 'var(--ink)' : 'var(--ink-2)' }}
            >
              Guide d'utilisation
            </button>
            <button
              type="button"
              onClick={() => navigate('/guide/sources')}
              className="rounded-md px-2 py-1.5 text-left text-xs"
              style={{ color: location.pathname === '/guide/sources' ? 'var(--ink)' : 'var(--ink-2)' }}
            >
              Sources
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-0.5 overflow-y-auto">
        <SectionHeader
          title="Conversations"
          open={conversationsOpen}
          onToggle={() => setConversationsOpen((o) => !o)}
        />
        {conversationsOpen && (
          <div className="flex flex-1 flex-col gap-2 overflow-y-auto pl-[19px] pr-1">
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
                const title =
                  conv.title ?? (conv.first_query ? deriveTitle(conv.first_query) : 'Nouvelle conversation')
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
          </div>
        )}
      </div>

      {/* Pinned at the bottom, always visible — placeholder only, no
          controls (functional content is feat/settings-panel). */}
      <div className="border-t pt-1" style={{ borderColor: 'var(--hairline)' }}>
        <SectionHeader
          icon={<IconSettings size={14} />}
          title="Réglages"
          open={settingsOpen}
          onToggle={() => setSettingsOpen((o) => !o)}
        />
        {settingsOpen && (
          <p className="px-2 pb-1 pl-[27px] text-xs" style={{ color: 'var(--ink-3)' }}>
            Aucun réglage disponible pour le moment.
          </p>
        )}
      </div>

      <div
        onMouseDown={() => {
          resizing.current = true
        }}
        className="absolute top-0 right-0 h-full w-1 cursor-col-resize"
        data-testid="sidebar-resize-handle"
      />
    </aside>
  )
}
