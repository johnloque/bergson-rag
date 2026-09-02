import { IconArrowRight } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ChunkNeighborSummary } from '../api/types'
import { formatCitation } from '../lib/citation'
import type { FocusedChunk } from '../lib/focusedChunk'

interface PositionFilmstripProps {
  focusedChunk: FocusedChunk
  onSelect: (chunk: ChunkNeighborSummary) => void
}

// Screen 4's second master-detail zone (docs/ROADMAP.md, Sprint 12
// `feat/chunk-neighbor-expansion`): textual position, not retrieval rank —
// deliberately styled to read as a different concept from the retrieval
// rail above it (dashed border + paper-2 muted background, vs. the rail's
// solid-bordered cards on plain paper). Neither this nor the rail ever
// shows full chunk text — both are compact selectors; the shared detail
// panel below is the only place full text renders.
export function PositionFilmstrip({ focusedChunk, onSelect }: PositionFilmstripProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['chunk-neighbors', focusedChunk.chunk_id],
    queryFn: () => api.getChunkNeighbors(focusedChunk.chunk_id),
  })

  return (
    <div
      className="flex items-stretch gap-3 rounded-xl p-3"
      style={{ background: 'var(--paper-2)', border: '1px dashed var(--hairline)' }}
      data-testid="position-filmstrip"
    >
      <FilmstripCell
        role="previous"
        label="Précédent"
        emptyLabel="Début de section"
        chunk={data?.previous ?? null}
        loading={isLoading}
        onSelect={onSelect}
      />
      <IconArrowRight size={16} className="my-auto shrink-0" style={{ color: 'var(--ink-3)' }} />
      <FilmstripCell
        role="current"
        label="Actuel"
        chunk={focusedChunk}
        loading={false}
        current
      />
      <IconArrowRight size={16} className="my-auto shrink-0" style={{ color: 'var(--ink-3)' }} />
      <FilmstripCell
        role="next"
        label="Suivant"
        emptyLabel="Fin de section"
        chunk={data?.next ?? null}
        loading={isLoading}
        onSelect={onSelect}
      />
    </div>
  )
}

interface FilmstripCellProps {
  role: 'previous' | 'current' | 'next'
  label: string
  emptyLabel?: string
  chunk: { chunk_id: string; work_id: string; paragraph_ids: string[] } | null
  loading: boolean
  current?: boolean
  onSelect?: (chunk: ChunkNeighborSummary) => void
}

// A null neighbor (section boundary reached, or the very start/end of the
// work) still renders its own cell — empty and disabled, not omitted — so
// the user sees there's no further neighbor in that direction rather than
// wondering why a cell is missing (docs/ROADMAP.md).
function FilmstripCell({ role, label, emptyLabel, chunk, loading, current, onSelect }: FilmstripCellProps) {
  const clickable = !current && chunk !== null && onSelect !== undefined

  return (
    <button
      type="button"
      data-testid={`filmstrip-cell-${role}`}
      disabled={!clickable}
      onClick={() => {
        if (clickable && chunk !== null) onSelect?.(chunk as ChunkNeighborSummary)
      }}
      className="flex min-w-[140px] flex-1 flex-col gap-1 rounded-lg p-2.5 text-left disabled:cursor-default"
      style={{
        background: current ? 'var(--paper)' : 'transparent',
        border: current ? '1.5px solid var(--red)' : '1px dashed var(--hairline)',
        opacity: chunk === null && !loading ? 0.5 : 1,
      }}
    >
      <span
        className="text-[10px] font-semibold uppercase"
        style={{ color: current ? 'var(--red)' : 'var(--ink-3)' }}
      >
        {label}
      </span>
      <span className="text-xs font-medium" style={{ color: 'var(--ink-2)' }}>
        {loading ? '…' : chunk ? formatCitation(chunk) : (emptyLabel ?? '—')}
      </span>
    </button>
  )
}
