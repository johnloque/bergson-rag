import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Wordmark } from '../components/Wordmark'
import { lastConversationPath } from '../lib/entry'

// Reached from Landing's "Commencer" once per session, and from clicking
// the wordmark/icon at any later point in the session (components/Sidebar.tsx)
// — the sole manual re-entry point into the pre-app screens, since Landing
// itself is never reachable by manual navigation (docs/frontend.md).
export function Presentation() {
  const navigate = useNavigate()
  const [entering, setEntering] = useState(false)

  async function handleEnter() {
    setEntering(true)
    const path = await lastConversationPath()
    navigate(path)
  }

  return (
    <div
      className="flex h-screen w-screen flex-col items-center justify-center gap-6 p-8"
      style={{ background: 'var(--paper)' }}
    >
      <Wordmark size={28} />
      {/* README's "What it does" paragraph, near-verbatim in French. */}
      <p className="max-w-md text-center text-sm" style={{ color: 'var(--ink-2)' }}>
        L'utilisateur pose une question en français, éventuellement restreinte par œuvre et/ou
        date de publication. Le système récupère et reclasse les passages pertinents, permet de
        les inspecter et de les sélectionner — en expliquant la pertinence de n'importe quel
        passage à la demande — puis ne génère une réponse synthétisée et citée qu'à la demande de
        l'utilisateur : l'examen des sources et la génération sont deux étapes distinctes, non un
        seul passage automatique.
      </p>
      <button
        type="button"
        onClick={handleEnter}
        disabled={entering}
        className="rounded-lg px-6 py-2 text-sm font-medium text-white disabled:opacity-60"
        style={{ background: 'var(--red)' }}
      >
        Entrer dans l'application
      </button>
    </div>
  )
}
