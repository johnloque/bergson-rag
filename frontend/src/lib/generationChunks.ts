// Derives, purely client-side, the citation for each chunk a generation
// actually included — the expandable detail under the "Génération de la
// réponse" step (components/GenerationBlock.tsx), reusing
// components/StepLine.tsx's existing children-slot/chevron exactly as
// lib/retrievalScope.ts does for the retrieval step, rather than a second
// disclosure implementation.
//
// The citation itself is lib/citation.ts's `formatCitation` — the same
// shared function components/ChunkRail.tsx calls for the chunk rail's own
// cards (docs/ROADMAP.md, Sprint 12: "Chunk card shows the real citation...
// instead of the raw chunk_id"), not a second, independently-hand-rolled
// format. This module used to render `{work title} ({year}) [{chunk_id}]`
// as a stand-in for a real citation display, before
// `feat/chunk-rail-and-citations` landed — that fallback is gone now that
// the real data path exists.

import type { ChunkResult } from '../api/types'
import { formatCitation } from './citation'

export interface IncludedChunkEntry {
  chunkId: string
  citation: string
}

// `chunks` is the turn's retrieved_chunks set (state/useTurnController.ts) —
// every chunk a generation could possibly have included is drawn from it,
// since /generate never retrieves beyond what /retrieve already persisted
// for the turn (src/api/main.py). A chunk_id with no match (e.g. a
// pre-migration row, or the chunk-text-snapshot limitation,
// docs/backend_api.md) has no ChunkResult to format a citation from, so it
// falls back to a plain "unknown work" label rather than crashing.
export function computeIncludedChunks(
  chunkIds: string[],
  chunks: ChunkResult[],
): IncludedChunkEntry[] {
  const byId = new Map(chunks.map((c) => [c.chunk_id, c]))
  return chunkIds.map((chunkId) => {
    const chunk = byId.get(chunkId)
    const citation = chunk ? formatCitation(chunk) : 'Œuvre inconnue'
    return { chunkId, citation }
  })
}
