import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { IconArrowLeft } from '@tabler/icons-react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { ChunkNeighborSummary, ChunkResult } from '../api/types'
import { ChunkRail } from '../components/ChunkRail'
import { PositionFilmstrip } from '../components/PositionFilmstrip'
import { RelevancePill } from '../components/RelevancePill'
import { formatCitation } from '../lib/citation'
import {
  focusedChunkFromNeighbor,
  focusedChunkFromResult,
  type FocusedChunk,
} from '../lib/focusedChunk'
import { MAX_INCLUDED_CHUNKS, useTurnUi } from '../state/turnUi'

// Screen 4 (docs/ROADMAP.md, Sprint 12 `feat/chunk-neighbor-expansion`):
// master-detail, not one chunk per route any more. Three stacked zones —
// the retrieval rail (pinned), the textual-position filmstrip, and one
// shared detail panel below both — all driven by a single `focusedChunk`
// piece of local state. Clicking a rail card or a filmstrip cell updates
// that state directly; neither ever navigates, which is what removes the
// old back-button/re-inspect friction of a chunk-per-route design. The URL
// still carries a `:chunkId` (unchanged route shape, App.tsx) — it only
// ever seeds the *initial* focus, once, on mount.
export function ChunkDetail() {
  const params = useParams()
  const navigate = useNavigate()
  const conversationId = Number(params.conversationId)
  const turnId = Number(params.turnId)
  const initialChunkId = params.chunkId as string
  const turnUi = useTurnUi()

  const [focusedChunk, setFocusedChunk] = useState<FocusedChunk | null>(null)

  const { data: turnDetail } = useQuery({
    queryKey: ['turn', turnId],
    queryFn: () => api.getTurn(turnId),
  })
  const retrievedChunks: ChunkResult[] = turnDetail?.retrieved_chunks ?? []

  // Seeds the shared inclusion state (state/turnUi.tsx) the same way
  // state/useTurnController.ts's own hydrate effect does — needed here too
  // since a direct visit/reload of this route never goes through that
  // hook, and isRetrieved()/getIncluded() below both depend on
  // `retrievedIds` having been set for this turn.
  useEffect(() => {
    if (!turnDetail) return
    turnUi.initTurn(
      turnId,
      turnDetail.retrieved_chunks.map((rc) => rc.chunk_id),
      turnDetail.chunk_judgments,
      turnDetail.included_chunk_ids,
      turnDetail.neighbor_chunks,
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turnDetail])

  // Resolves the URL's initial :chunkId exactly once, from whichever
  // source actually has it — the turn's retrieved chunks, or (a
  // neighbor-origin chunk navigated here via a Screen 3 "Inspecter" click)
  // turnUi's own neighbor map. A direct reload landing on a neighbor-origin
  // id has neither (that map is client-only, Sprint 8's addendum) — the
  // detail panel below falls back to a placeholder rather than fabricating
  // content, same accepted limitation as the chunk-text-snapshot case
  // (docs/frontend.md).
  useEffect(() => {
    if (focusedChunk || !turnDetail) return
    const retrieved = turnDetail.retrieved_chunks.find((rc) => rc.chunk_id === initialChunkId)
    if (retrieved) {
      setFocusedChunk(focusedChunkFromResult(retrieved))
      return
    }
    const neighbor = turnUi.getNeighborChunks(turnId).find((c) => c.chunk_id === initialChunkId)
    if (neighbor) setFocusedChunk(focusedChunkFromNeighbor(neighbor))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turnDetail, initialChunkId])

  function handleInspect(chunk: ChunkResult | ChunkNeighborSummary) {
    setFocusedChunk('score' in chunk ? focusedChunkFromResult(chunk) : focusedChunkFromNeighbor(chunk))
  }

  const isRetrieved = focusedChunk !== null && turnUi.isRetrieved(turnId, focusedChunk.chunk_id)
  const included = focusedChunk !== null && turnUi.getIncluded(turnId, focusedChunk.chunk_id)
  const includedCount = turnUi.getIncludedCount(turnId)
  const includeDisabled = !included && includedCount >= MAX_INCLUDED_CHUNKS

  function handleToggleInclude() {
    if (!focusedChunk) return
    if (isRetrieved) {
      turnUi.toggleChunk(turnId, focusedChunk.chunk_id)
      return
    }
    if (focusedChunk.section_id === null) return
    turnUi.toggleNeighborChunk(turnId, {
      chunk_id: focusedChunk.chunk_id,
      work_id: focusedChunk.work_id,
      section_id: focusedChunk.section_id,
      section_path: focusedChunk.section_path,
      paragraph_ids: focusedChunk.paragraph_ids,
      page_start: focusedChunk.page_start,
      page_end: focusedChunk.page_end,
      text: focusedChunk.text,
    })
  }

  const judgment = focusedChunk ? turnUi.getJudgment(turnId, focusedChunk.chunk_id) : undefined

  const judgeMutation = useMutation({
    mutationFn: () => {
      if (!focusedChunk || !turnDetail) throw new Error('chunk or turn not loaded')
      return api.judgeChunk({
        query: turnDetail.query,
        chunk: {
          chunk_id: focusedChunk.chunk_id,
          text: focusedChunk.text,
          work_id: focusedChunk.work_id,
          section_path: focusedChunk.section_path,
          paragraph_ids: focusedChunk.paragraph_ids,
          page_start: focusedChunk.page_start,
          page_end: focusedChunk.page_end,
          score: focusedChunk.score,
        },
        turn_id: turnId,
      })
    },
    onSuccess: (result) => focusedChunk && turnUi.setJudgment(turnId, focusedChunk.chunk_id, result),
  })

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
      <button
        type="button"
        onClick={() => navigate(`/c/${conversationId}`)}
        className="flex items-center gap-1.5 self-start text-sm"
        style={{ color: 'var(--ink-2)' }}
      >
        <IconArrowLeft size={16} />
        Retour
      </button>

      {/* Zone 1 — retrieval rail, pinned, reused exactly as Screen 3 uses
          it: same cards, same include/exclude toggle, same x/5 counter.
          Only difference is `onInspect`, which routes a click into local
          focus state instead of navigating (components/ChunkRail.tsx). */}
      <ChunkRail
        chunks={retrievedChunks}
        turnId={turnId}
        conversationId={conversationId}
        onInspect={handleInspect}
      />

      {/* Zone 2 — textual-position filmstrip, distinct look (dashed
          border, paper-2 background) so it reads as a different concept
          from the rail above at a glance. */}
      {focusedChunk && (
        <PositionFilmstrip
          focusedChunk={focusedChunk}
          anchors={retrievedChunks}
          onSelect={(chunk) => setFocusedChunk(focusedChunkFromNeighbor(chunk))}
        />
      )}

      {/* Zone 3 — the one shared detail panel, driven by focusedChunk
          regardless of which selector set it. */}
      {focusedChunk ? (
        <div className="grid grid-cols-[1fr_260px] gap-6">
          <div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm" style={{ color: 'var(--ink-3)' }} data-testid="focused-chunk-citation">
                {formatCitation(focusedChunk)}
              </span>
              <span
                data-testid="chunk-origin-tag"
                className="rounded-full px-2 py-0.5 text-[11px] font-medium"
                style={{
                  color: isRetrieved ? 'var(--ink-2)' : 'var(--red)',
                  background: isRetrieved ? 'var(--paper-2)' : 'var(--red-bg)',
                }}
              >
                {isRetrieved ? 'Depuis la recherche' : 'Voisin — hors des résultats de recherche'}
              </span>
            </div>
            <div
              className="mt-2 rounded-xl p-4"
              style={{ background: 'var(--paper-2)', border: '0.5px solid var(--hairline)' }}
            >
              <p
                data-testid="focused-chunk-text"
                className="whitespace-pre-wrap text-[15px] leading-relaxed"
                style={{ color: 'var(--ink)' }}
              >
                {focusedChunk.text || 'Texte indisponible pour ce passage (session précédente).'}
              </p>
            </div>
            {focusedChunk.score !== null && (
              <p className="mt-2 font-mono text-xs" style={{ color: 'var(--ink-3)' }}>
                score {focusedChunk.score.toFixed(2)}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => judgeMutation.mutate()}
                disabled={judgeMutation.isPending}
                className="flex-1 rounded-lg py-1.5 text-sm font-medium text-white disabled:opacity-50"
                style={{ background: 'var(--red)' }}
              >
                {judgeMutation.isPending ? 'Analyse…' : 'Expliquer'}
              </button>
              <button
                type="button"
                onClick={handleToggleInclude}
                disabled={includeDisabled}
                title={includeDisabled ? `Maximum ${MAX_INCLUDED_CHUNKS} passages sélectionnés` : undefined}
                className="flex-1 rounded-lg border py-1.5 text-sm font-medium disabled:opacity-50"
                style={{ borderColor: 'var(--hairline)', color: 'var(--ink)' }}
              >
                {included ? 'Exclure' : 'Inclure'}
              </button>
            </div>

            {judgment && (
              <div className="flex flex-col gap-2">
                <RelevancePill label={judgment.label} />
                <p className="text-[13px]" style={{ color: 'var(--ink-2)' }}>
                  {judgment.justification}
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <p className="text-sm" style={{ color: 'var(--ink-3)' }}>
          Chargement du passage…
        </p>
      )}
    </div>
  )
}
