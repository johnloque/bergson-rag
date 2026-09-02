// Screen 4's master-detail restructure (docs/ROADMAP.md, Sprint 12
// `feat/chunk-neighbor-expansion`): the detail panel is driven by whichever
// chunk is currently "focused", regardless of whether that came from the
// retrieval rail (a real, scored `ChunkResult`) or the position filmstrip
// (a `ChunkNeighborSummary` resolved by adjacency, no score). `FocusedChunk`
// is the one shape the detail panel renders against, so it doesn't need to
// branch on which of the two response shapes produced it.

import type { ChunkNeighborSummary, ChunkResult, PageRef } from '../api/types'
import type { CitableChunk } from './citation'

export interface FocusedChunk extends CitableChunk {
  chunk_id: string
  section_path: string
  page_start: PageRef
  page_end: PageRef
  text: string
  // null for a neighbor-origin chunk — it was never retrieved/ranked, so
  // there is no score to show (the detail panel omits the score line
  // entirely rather than fabricating one).
  score: number | null
  // Only ever set for a chunk that arrived as a `ChunkNeighborSummary`
  // (the position filmstrip, or a neighbor-origin rail card) — `ChunkResult`
  // carries no `section_id` at all (src/api/schemas.py). Needed to rebuild
  // a full `ChunkNeighborSummary` if this chunk gets included from the
  // detail panel (state/turnUi.tsx's `toggleNeighborChunk`); null for a
  // rail-origin chunk, which never needs one (it's included via the plain
  // `toggleChunk` action instead).
  section_id: string | null
}

export function focusedChunkFromResult(chunk: ChunkResult): FocusedChunk {
  return {
    chunk_id: chunk.chunk_id,
    work_id: chunk.work_id,
    section_path: chunk.section_path,
    paragraph_ids: chunk.paragraph_ids,
    page_start: chunk.page_start,
    page_end: chunk.page_end,
    text: chunk.text,
    score: chunk.score,
    section_id: null,
  }
}

export function focusedChunkFromNeighbor(chunk: ChunkNeighborSummary): FocusedChunk {
  return {
    chunk_id: chunk.chunk_id,
    work_id: chunk.work_id,
    section_path: chunk.section_path,
    paragraph_ids: chunk.paragraph_ids,
    page_start: chunk.page_start,
    page_end: chunk.page_end,
    text: chunk.text,
    score: null,
    section_id: chunk.section_id,
  }
}
