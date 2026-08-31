// Derives, purely client-side, the work+citation label for each chunk a
// generation actually included — the expandable detail under the
// "Génération de la réponse" step (components/GenerationBlock.tsx), reusing
// components/StepLine.tsx's existing children-slot/chevron exactly as
// lib/retrievalScope.ts does for the retrieval step, rather than a second
// disclosure implementation.
//
// `work + citation`: work title comes from the static lib/works.ts mirror
// (falling back to the raw work_id if a chunk's work isn't in that table —
// shouldn't happen against the real 8-work corpus, but a chunk's work_id
// could be unresolved if `chunks` doesn't have it, see below); the citation
// is the chunk's own `[chunk_id]` — the same bracketed identifier the
// generation prompt's citation format and Layer 1's structural check both
// key on (docs/anti_hallucination_guardrails.md), used here as a stand-in
// for a real citation display (work, year, page, paragraph) until
// `feat/chunk-rail-and-citations` lands (docs/ROADMAP.md, Sprint 12).

import type { ChunkResult } from '../api/types'
import { WORKS } from './works'

const WORKS_BY_ID = new Map(WORKS.map((w) => [w.id, w]))

export interface IncludedChunkEntry {
  chunkId: string
  workId: string
  workLabel: string
}

// `chunks` is the turn's retrieved_chunks set (state/useTurnController.ts) —
// every chunk a generation could possibly have included is drawn from it,
// since /generate never retrieves beyond what /retrieve already persisted
// for the turn (src/api/main.py). A chunk_id with no match (e.g. a
// pre-migration row, or the chunk-text-snapshot limitation,
// docs/backend_api.md) falls back to the bare chunk_id with no work label.
export function computeIncludedChunks(
  chunkIds: string[],
  chunks: ChunkResult[],
): IncludedChunkEntry[] {
  const byId = new Map(chunks.map((c) => [c.chunk_id, c]))
  return chunkIds.map((chunkId) => {
    const chunk = byId.get(chunkId)
    const workId = chunk?.work_id ?? ''
    const work = WORKS_BY_ID.get(workId)
    const workLabel = work ? `${work.title} (${work.year})` : workId || 'Œuvre inconnue'
    return { chunkId, workId, workLabel }
  })
}
