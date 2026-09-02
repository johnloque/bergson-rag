import type { ChunkInput, ChunkNeighborSummary, ChunkResult } from '../api/types'

export function toChunkInput(chunk: ChunkResult): ChunkInput {
  return {
    chunk_id: chunk.chunk_id,
    text: chunk.text,
    work_id: chunk.work_id,
    section_path: chunk.section_path,
    paragraph_ids: chunk.paragraph_ids,
    page_start: chunk.page_start,
    page_end: chunk.page_end,
    score: chunk.score,
  }
}

// A neighbor chunk (Sprint 12 `feat/chunk-neighbor-expansion`) was never
// retrieved/ranked, so it has no score to resend — `null`, the same value
// ChunkInput.score already accepts for a hand-curated chunk with no
// retrieval signal (src/api/schemas.py's ChunkInput docstring).
export function neighborSummaryToChunkInput(chunk: ChunkNeighborSummary): ChunkInput {
  return {
    chunk_id: chunk.chunk_id,
    text: chunk.text,
    work_id: chunk.work_id,
    section_path: chunk.section_path,
    paragraph_ids: chunk.paragraph_ids,
    page_start: chunk.page_start,
    page_end: chunk.page_end,
    score: null,
  }
}
