import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { ChunkResult, RetrievalConfidenceTier } from '../api/types'
import { useTurnUi } from '../state/turnUi'
import { ConfidenceGauge } from './ConfidenceGauge'

interface ChunkRailProps {
  chunks: ChunkResult[]
  turnId: number | null
  conversationId: number | null
}

// The confidence gauge lives here, above the rail, not in the post-
// evaluation answer card (docs/ROADMAP.md, the retrieval-confidence-split
// correction): it's advisory input to the decision to generate/regenerate,
// so it has to be visible *before* that decision, recomputed live from
// whichever chunks are currently included. Debounced so a burst of rapid
// include/exclude clicks doesn't fire a request per click.
const CONFIDENCE_PREVIEW_DEBOUNCE_MS = 300

export function ChunkRail({ chunks, turnId, conversationId }: ChunkRailProps) {
  const turnUi = useTurnUi()
  const navigate = useNavigate()
  const [confidenceTier, setConfidenceTier] = useState<RetrievalConfidenceTier | null>(null)

  const includedChunks = chunks.filter((chunk) =>
    turnId !== null ? turnUi.getIncluded(turnId, chunk.chunk_id) : true,
  )
  const includedKey = includedChunks.map((c) => `${c.chunk_id}:${c.score}`).join('|')

  useEffect(() => {
    if (includedChunks.length === 0) {
      setConfidenceTier(null)
      return
    }
    const handle = window.setTimeout(() => {
      void api
        .confidencePreview({
          chunks: includedChunks.map((c) => ({ chunk_id: c.chunk_id, score: c.score })),
        })
        .then((result) => setConfidenceTier(result.retrieval_confidence_tier))
        .catch(() => setConfidenceTier(null))
    }, CONFIDENCE_PREVIEW_DEBOUNCE_MS)
    return () => window.clearTimeout(handle)
    // includedKey is the real dependency (chunk identity/score/inclusion) —
    // includedChunks itself is a fresh array every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includedKey])

  if (chunks.length === 0) return null

  return (
    <div className="flex flex-col gap-2">
      {confidenceTier && <ConfidenceGauge tier={confidenceTier} />}
      <div className="flex gap-3 overflow-x-auto pb-1" data-testid="chunk-rail">
        {chunks.map((chunk) => {
          const included = turnId !== null ? turnUi.getIncluded(turnId, chunk.chunk_id) : true
          return (
            <div
              key={chunk.chunk_id}
              data-testid={`chunk-card-${chunk.chunk_id}`}
              data-included={included}
              className="flex w-[130px] shrink-0 flex-col gap-1.5 rounded-lg p-2.5"
              style={{
                background: 'var(--paper)',
                border: included ? '1.5px solid var(--red)' : '0.5px solid var(--hairline)',
                opacity: included ? 1 : 0.55,
              }}
            >
              <span
                className="text-[10px] font-semibold uppercase"
                style={{ color: included ? 'var(--red)' : 'var(--ink-3)' }}
              >
                {included ? 'Inclus' : 'Exclu'}
              </span>
              <span className="truncate text-xs font-medium" style={{ color: 'var(--ink-2)' }}>
                {chunk.work_id || '—'}
              </span>
              <p
                className="text-xs"
                style={{
                  color: 'var(--ink)',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}
              >
                {chunk.text || 'Texte indisponible (nouvelle recherche requise).'}
              </p>
              <div className="mt-auto flex flex-col gap-1">
                <button
                  type="button"
                  onClick={() => turnId !== null && turnUi.toggleChunk(turnId, chunk.chunk_id)}
                  disabled={turnId === null}
                  className="rounded border px-2 py-1 text-[11px]"
                  style={{ borderColor: 'var(--hairline)', color: 'var(--ink-2)' }}
                >
                  {included ? 'Exclure' : 'Inclure'}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    turnId !== null &&
                    conversationId !== null &&
                    navigate(`/c/${conversationId}/turn/${turnId}/chunk/${chunk.chunk_id}`)
                  }
                  disabled={turnId === null}
                  className="rounded border px-2 py-1 text-[11px] font-medium"
                  style={{ borderColor: 'var(--hairline)', color: 'var(--ink)' }}
                >
                  Inspecter
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
