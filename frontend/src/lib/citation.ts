// The single citation display format for a retrieved chunk — used
// identically by the chunk rail/detail cards (components/ChunkRail.tsx,
// routes/ChunkDetail.tsx) and the answer card's included-chunks bullet
// list (lib/generationChunks.ts, components/GenerationBlock.tsx), per
// docs/ROADMAP.md's Sprint 12 "Chunk card shows the real citation" item
// (`feat/chunk-rail-and-citations`). One shared function, imported by both,
// rather than two hand-rolled copies of the same format drifting apart.
//
// Mirrors src.works.resolve_paragraph_metadata (src/works.py) at display
// granularity — same manual-mirror convention lib/works.ts already uses
// for WORKS/TEXTS (no shared build step between the Python backend and
// this Vite frontend).
//
// Three shapes, depending on what resolveParagraphMetadata below returns:
//  - non-anthology work (or an anthology chunk falling back to work-level
//    only — front matter, no covering individually-dated text):
//    "{work_title} ({work_year}), paragraphe {n}"
//  - anthology work (1919_ES/1934_PM) resolving to a specific
//    individually-dated text: "{work_title} ({work_year}) — {text_title}
//    ({text_year}), paragraphe {n}"
//
// `chunk.paragraph_ids[0]` is used as the paragraph number, not a
// min-max range over every element: src/ingestion/chunking.py's chunking
// scheme makes one chunk = one paragraph, so `paragraph_ids` always has
// exactly one element in the real corpus (verified by reading that
// module, not assumed) — same "index 0 is representative of the whole
// chunk" convention src/generation/prompt.py already relies on for this
// exact field. No paragraph-range formatting ("paragraphes {n}-{m}") is
// implemented, since no chunk in this project can ever span more than one
// paragraph to need it.

import type { ChunkResult } from '../api/types'
import { ANTHOLOGY_WORK_IDS, TEXTS, WORKS, type TextOption } from './works'

const WORKS_BY_ID = new Map(WORKS.map((w) => [w.id, w]))

const PARAGRAPH_INDEX_PATTERN = /_p(\d+)$/

function paragraphIndex(paragraphId: string | undefined): number | null {
  if (!paragraphId) return null
  const match = paragraphId.match(PARAGRAPH_INDEX_PATTERN)
  return match ? Number(match[1]) : null
}

// Mirrors src.works.resolve_paragraph_metadata's text-level lookup: None
// (here, `undefined`) for a non-anthology work_id, front/back matter, or a
// paragraph index outside every recorded range for its work.
function resolveText(workId: string, index: number): TextOption | undefined {
  if (!ANTHOLOGY_WORK_IDS.includes(workId)) return undefined
  return (TEXTS[workId] ?? []).find((t) => index >= t.paragraphStart && index <= t.paragraphEnd)
}

export function formatCitation(chunk: ChunkResult): string {
  const work = WORKS_BY_ID.get(chunk.work_id)
  const workTitle = work ? work.title : chunk.work_id || 'Œuvre inconnue'
  const workYearPart = work ? ` (${work.year})` : ''

  const index = paragraphIndex(chunk.paragraph_ids[0])
  const paragraphPart = index !== null ? `, paragraphe ${index}` : ''

  const text = index !== null ? resolveText(chunk.work_id, index) : undefined
  if (text) {
    return `${workTitle}${workYearPart} — ${text.title} (${text.year})${paragraphPart}`
  }
  return `${workTitle}${workYearPart}${paragraphPart}`
}
