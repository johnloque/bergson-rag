import type { ChunkInput, ChunkResult } from '../api/types'

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
