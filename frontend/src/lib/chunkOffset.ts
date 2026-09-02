// Distance display for a neighbor chunk (docs/ROADMAP.md, Sprint 12
// `feat/chunk-neighbor-expansion` refinement): "+1"/"-2"/etc. relative to
// whichever originally-retrieved chunk it's closest to, in the same work.
//
// Computed purely from `paragraph_ids`, not tracked through navigation —
// one chunk = one paragraph (src/ingestion/chunking.py, see
// lib/citation.ts's own comment), so the paragraph index already IS the
// chunk's linear position; the offset between any two chunks in the same
// work is just the difference of their paragraph indices. No state needs
// threading through PositionFilmstrip's prev/next clicks or through
// state/turnUi.tsx's `neighbors` map to get this right.

import { paragraphIndex } from './citation'

export interface OffsetAnchorChunk {
  work_id: string
  paragraph_ids: string[]
}

// `null` when `chunk` or every same-work anchor lacks a parseable
// paragraph index, or when `anchors` has no chunk from the same work at
// all (a neighbor should never be reachable outside the anchors' work, but
// this stays a display-only fallback rather than a thrown error either
// way).
export function distanceFromNearestAnchor(
  chunk: OffsetAnchorChunk,
  anchors: OffsetAnchorChunk[],
): number | null {
  const chunkIndex = paragraphIndex(chunk.paragraph_ids[0])
  if (chunkIndex === null) return null
  let best: number | null = null
  for (const anchor of anchors) {
    if (anchor.work_id !== chunk.work_id) continue
    const anchorIndex = paragraphIndex(anchor.paragraph_ids[0])
    if (anchorIndex === null) continue
    const diff = chunkIndex - anchorIndex
    if (best === null || Math.abs(diff) < Math.abs(best)) best = diff
  }
  return best
}

export function formatOffset(offset: number): string {
  return offset > 0 ? `+${offset}` : String(offset)
}
