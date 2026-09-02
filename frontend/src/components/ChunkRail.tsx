import { useEffect, useState } from 'react'
import { IconArrowsExchange } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { ChunkNeighborSummary, ChunkResult, RetrievalConfidenceTier } from '../api/types'
import { formatCitation } from '../lib/citation'
import { MAX_INCLUDED_CHUNKS, useTurnUi } from '../state/turnUi'
import { ConfidenceGauge } from './ConfidenceGauge'

interface ChunkRailProps {
  chunks: ChunkResult[]
  turnId: number | null
  conversationId: number | null
  /** Screen 4's master-detail view (routes/ChunkDetail.tsx) passes this so
   * "Inspecter" sets the shared detail panel's focused chunk in place
   * instead of navigating — the rail is otherwise reused completely as-is
   * (docs/ROADMAP.md, Sprint 12 `feat/chunk-neighbor-expansion`). Screen 3
   * (components/TurnCard.tsx) leaves this unset, keeping the original
   * navigate-to-Screen-4 behavior. */
  onInspect?: (chunk: ChunkResult | ChunkNeighborSummary) => void
}

// The confidence gauge lives here, above the rail, not in the post-
// evaluation answer card (docs/ROADMAP.md, the retrieval-confidence-split
// correction): it's advisory input to the decision to generate/regenerate,
// so it has to be visible *before* that decision, recomputed live from
// whichever chunks are currently included. Debounced so a burst of rapid
// include/exclude clicks doesn't fire a request per click.
const CONFIDENCE_PREVIEW_DEBOUNCE_MS = 300

export function ChunkRail({ chunks, turnId, conversationId, onInspect }: ChunkRailProps) {
  const turnUi = useTurnUi()
  const navigate = useNavigate()
  const [confidenceTier, setConfidenceTier] = useState<RetrievalConfidenceTier | null>(null)

  // Sprint 12 `feat/chunk-neighbor-expansion`: the rail represents the FULL
  // set of chunks that will be sent to generation, not just the 15
  // retrieved candidates — a chunk included via Screen 4's neighbor
  // exploration is appended after them (state/turnUi.tsx's `neighbors` map,
  // the single shared source of truth Screen 3 and Screen 4 both read).
  // Always included by definition (existence in that map IS its inclusion
  // state — see turnUi.tsx), so no separate "excluded neighbor" case to
  // filter here.
  const neighborChunks = turnId !== null ? turnUi.getNeighborChunks(turnId) : []

  const includedChunks = chunks.filter((chunk) =>
    turnId !== null ? turnUi.getIncluded(turnId, chunk.chunk_id) : true,
  )
  const includedKey = [...includedChunks.map((c) => `${c.chunk_id}:${c.score}`), ...neighborChunks.map((c) => c.chunk_id)].join('|')

  useEffect(() => {
    const previewChunks = [
      ...includedChunks.map((c) => ({ chunk_id: c.chunk_id, score: c.score })),
      ...neighborChunks.map((c) => ({ chunk_id: c.chunk_id, score: null })),
    ]
    if (previewChunks.length === 0) {
      setConfidenceTier(null)
      return
    }
    const handle = window.setTimeout(() => {
      void api
        .confidencePreview({ chunks: previewChunks })
        .then((result) => setConfidenceTier(result.retrieval_confidence_tier))
        .catch(() => setConfidenceTier(null))
    }, CONFIDENCE_PREVIEW_DEBOUNCE_MS)
    return () => window.clearTimeout(handle)
    // includedKey is the real dependency (chunk identity/score/inclusion) —
    // includedChunks/neighborChunks are fresh arrays every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includedKey])

  if (chunks.length === 0) return null

  // docs/ROADMAP.md, Sprint 12: at most MAX_INCLUDED_CHUNKS selectable at
  // once, rail-origin and neighbor-origin combined — the reducer
  // (state/turnUi.tsx) is what actually blocks a 6th inclusion (a true
  // no-op, shared with routes/ChunkDetail.tsx's own toggle), this is only
  // the rail's own "clear indication" of the cap: a running count, and
  // disabling "Inclure" on every currently-excluded card once it's reached.
  const includedCount =
    turnId !== null ? turnUi.getIncludedCount(turnId) : includedChunks.length
  const atCap = includedCount >= MAX_INCLUDED_CHUNKS

  function inspect(chunk: ChunkResult | ChunkNeighborSummary) {
    if (onInspect) {
      onInspect(chunk)
      return
    }
    if (turnId !== null && conversationId !== null) {
      navigate(`/c/${conversationId}/turn/${turnId}/chunk/${chunk.chunk_id}`)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {confidenceTier && <ConfidenceGauge tier={confidenceTier} />}
      <p className="text-xs" style={{ color: 'var(--ink-3)' }} data-testid="included-count">
        {includedCount}/{MAX_INCLUDED_CHUNKS} passages sélectionnés
        {atCap && ' (maximum atteint)'}
      </p>
      <div className="flex gap-3 overflow-x-auto pb-1" data-testid="chunk-rail">
        {chunks.map((chunk) => {
          const included = turnId !== null ? turnUi.getIncluded(turnId, chunk.chunk_id) : true
          const includeDisabled = turnId === null || (!included && atCap)
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
              <span
                data-testid="chunk-citation"
                className="text-xs font-medium"
                style={{
                  color: 'var(--ink-2)',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}
              >
                {formatCitation(chunk)}
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
                  disabled={includeDisabled}
                  title={!included && atCap ? `Maximum ${MAX_INCLUDED_CHUNKS} passages sélectionnés` : undefined}
                  className="rounded border px-2 py-1 text-[11px] disabled:opacity-50"
                  style={{ borderColor: 'var(--hairline)', color: 'var(--ink-2)' }}
                >
                  {included ? 'Exclure' : 'Inclure'}
                </button>
                <button
                  type="button"
                  onClick={() => inspect(chunk)}
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

        {neighborChunks.length > 0 && (
          <>
            {/* Thin dashed vertical divider (docs/ROADMAP.md, Sprint 12):
                marks where the retrieved 15 end and manually-added
                neighbor-origin chunks begin. */}
            <div
              className="my-1 w-0 shrink-0 self-stretch"
              style={{ borderLeft: '1px dashed var(--hairline)' }}
              data-testid="neighbor-divider"
            />
            {neighborChunks.map((chunk) => (
              <div
                key={chunk.chunk_id}
                data-testid={`chunk-card-${chunk.chunk_id}`}
                data-included="true"
                data-origin="neighbor"
                className="flex w-[130px] shrink-0 flex-col gap-1.5 rounded-lg p-2.5"
                style={{ background: 'var(--paper)', border: '1.5px dashed var(--red)' }}
              >
                <span
                  className="flex items-center gap-1 text-[10px] font-semibold uppercase"
                  style={{ color: 'var(--red)' }}
                >
                  <IconArrowsExchange size={11} />
                  Inclus
                </span>
                <span
                  data-testid="chunk-citation"
                  className="text-xs font-medium"
                  style={{
                    color: 'var(--ink-2)',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}
                >
                  {formatCitation(chunk)}
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
                    onClick={() => turnId !== null && turnUi.toggleNeighborChunk(turnId, chunk)}
                    className="rounded border px-2 py-1 text-[11px]"
                    style={{ borderColor: 'var(--hairline)', color: 'var(--ink-2)' }}
                  >
                    Exclure
                  </button>
                  <button
                    type="button"
                    onClick={() => inspect(chunk)}
                    disabled={turnId === null}
                    className="rounded border px-2 py-1 text-[11px] font-medium"
                    style={{ borderColor: 'var(--hairline)', color: 'var(--ink)' }}
                  >
                    Inspecter
                  </button>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
