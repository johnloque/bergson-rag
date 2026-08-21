import { useNavigate } from 'react-router-dom'
import type { ChunkResult } from '../api/types'
import { useTurnUi } from '../state/turnUi'

interface ChunkRailProps {
  chunks: ChunkResult[]
  turnId: number | null
  conversationId: number | null
}

export function ChunkRail({ chunks, turnId, conversationId }: ChunkRailProps) {
  const turnUi = useTurnUi()
  const navigate = useNavigate()

  if (chunks.length === 0) return null

  return (
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
  )
}
