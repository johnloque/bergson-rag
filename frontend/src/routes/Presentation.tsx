import { IconListSearch, IconSparkles } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { AbstractGraphic } from '../components/AbstractGraphic'

// A sidebar destination like GuideUtilisation and Sources, nested under
// AppShell — reached from Landing's "Commencer" and from clicking the
// wordmark/icon at any later point (components/Sidebar.tsx). No longer a
// standalone pre-app screen: since it renders inside AppShell, the sidebar
// itself (conversation list, "Nouvelle conversation") is the way into the
// app, so there's no separate "enter" step here (docs/frontend.md).
export function Presentation() {
  const navigate = useNavigate()

  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-8 p-12 text-center">
      <div className="flex flex-col items-center gap-4">
        <AbstractGraphic size={70} />
        <p className="font-wordmark text-[26px] font-medium" style={{ color: 'var(--ink)' }}>
          Bienvenue sur Bergson-RAG !
        </p>
      </div>

      <p className="mx-auto max-w-[480px] text-sm" style={{ color: 'var(--ink-2)' }}>
        Un outil pour vous assister dans vos recherches sur la philosophie d'Henri Bergson, que
        vous soyez expert de cet auteur ou simplement curieux de découvrir sa pensée.
      </p>

      <blockquote
        className="font-wordmark mx-auto max-w-[520px] py-6 text-base italic"
        style={{
          color: 'var(--ink)',
          borderTop: '0.5px solid var(--hairline)',
          borderBottom: '0.5px solid var(--hairline)',
        }}
      >
        Elle ne remplace pas une lecture rapprochée de ses textes : elle en propose une approche
        algorithmique complémentaire, capable de faire émerger des régularités à l'échelle de
        l'œuvre complète — une tâche impossible à réaliser à la main.
      </blockquote>

      <div className="mx-auto flex w-full max-w-[560px] gap-4">
        <div
          className="flex flex-1 flex-col gap-2 rounded-xl p-5 text-left"
          style={{ border: '0.5px solid var(--hairline)' }}
        >
          <IconListSearch size={20} style={{ color: 'var(--red)' }} />
          <p className="text-sm font-medium" style={{ color: 'var(--ink)' }}>
            Le retrieval
          </p>
          <p className="text-xs" style={{ color: 'var(--ink-2)' }}>
            Un moteur de recherche sémantique : il retrouve, pour votre question, les passages les
            plus pertinents du corpus — les chunks — classés par score de similarité.
          </p>
        </div>
        <div
          className="flex flex-1 flex-col gap-2 rounded-xl p-5 text-left"
          style={{ border: '0.5px solid var(--hairline)' }}
        >
          <IconSparkles size={20} style={{ color: 'var(--red)' }} />
          <p className="text-sm font-medium" style={{ color: 'var(--ink)' }}>
            La génération
          </p>
          <p className="text-xs" style={{ color: 'var(--ink-2)' }}>
            Une synthèse en langage naturel des passages que vous avez retenus à l'étape
            précédente.
          </p>
        </div>
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => navigate('/guide/utilisation')}
          className="rounded-lg px-6 py-2 text-sm"
          style={{ background: 'var(--paper)', border: '0.5px solid var(--hairline)', color: 'var(--ink)' }}
        >
          Guide d'utilisation
        </button>
        {/* Same effect as Sidebar's "Nouvelle conversation" button. */}
        <button
          type="button"
          onClick={() => navigate('/new')}
          className="rounded-lg px-6 py-2 text-sm font-medium text-white"
          style={{ background: 'var(--red)' }}
        >
          Poser ma première question
        </button>
      </div>
    </div>
  )
}
