import type { ChunkResult } from '../api/types'

// In-memory, module-level cache of full chunk content (text, work_id,
// section_path, page refs) keyed by chunk_id — globally unique across the
// corpus, so no per-turn namespacing is needed.
//
// Why this exists: `retrieved_chunks` (src/api/models.py) persists only
// chunk_id/rank/score, never chunk text. `GET /turns/{id}` re-fetches text
// live from Qdrant (src/api/main.py:get_turn) so a fresh page load recovers
// it too — this cache just avoids redundant hydration work when navigating
// between the rail and the chunk detail view within a session. It only
// falls short of a stored snapshot for the reindex edge case
// (docs/backend_api.md's accepted limitation): a chunk_id no longer indexed
// comes back with empty text from both the server and this cache, and
// components fall back to a placeholder rather than fabricating content.
const cache = new Map<string, ChunkResult>()

export function cacheChunks(chunks: ChunkResult[]): void {
  for (const chunk of chunks) cache.set(chunk.chunk_id, chunk)
}

export function getCachedChunk(chunkId: string): ChunkResult | undefined {
  return cache.get(chunkId)
}
