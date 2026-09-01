// Derives, purely client-side from a turn's filter params, which works
// ("publication" mode / no date_range) or individual anthology texts
// ("text" mode) were actually left in scope for that turn's retrieval —
// the expandable detail under the "Recherche des passages pertinents"
// step (components/StepLine.tsx, components/TurnCard.tsx). Mirrors the
// backend's eligibility logic (src/retrieval/filtering.py) at display
// granularity only, using the static lib/works.ts mirror — no API call.

import { ALL_WORK_IDS, ANTHOLOGY_WORK_IDS, TEXTS, WORKS } from './works'
import type { RetrieveFilterParams } from '../state/retrievalFilter'

export interface ConsideredWorkEntry {
  workId: string
  title: string
  year: number
  // Only set for an anthology work under "text" mode with a date_range —
  // the individual dated texts (src.works.TEXTS) that fall in range.
  // Undefined for a work included at whole-work granularity ("publication"
  // mode, no date_range at all, or a non-anthology work).
  texts?: { title: string; year: number }[]
}

const WORKS_BY_ID = new Map(WORKS.map((w) => [w.id, w]))

// Returns null when filterParams is unknown — a reloaded/hydrated turn
// (GET /turns/{id}), whose applied filter (if any) this branch does not
// persist server-side (docs/frontend.md). Never guessed as "unfiltered":
// the caller renders no expand affordance at all for that case rather than
// risk showing a wrong list.
export function computeConsideredSources(
  filterParams: RetrieveFilterParams | undefined,
): ConsideredWorkEntry[] | null {
  if (!filterParams) return null

  const allowedIds = filterParams.work_ids ?? ALL_WORK_IDS
  const range = filterParams.date_range

  const entries: ConsideredWorkEntry[] = []
  for (const workId of allowedIds) {
    const work = WORKS_BY_ID.get(workId)
    if (!work) continue

    if (range && range.mode === 'text' && ANTHOLOGY_WORK_IDS.includes(workId)) {
      // Individually-dated texts only — this display intentionally omits
      // the backend's undated-front-matter fallback to the work-level
      // year (src.works.resolve_paragraph_metadata), a handful of
      // paragraphs per anthology at most: an accepted simplification for
      // this summary, not a claim that it matches matches_date_range
      // exactly paragraph-for-paragraph.
      const texts = (TEXTS[workId] ?? [])
        .filter((t) => t.year >= range.start && t.year <= range.end)
        // Display-only: this summary only ever needs title/year (unlike
        // lib/citation.ts's resolveParagraphMetadata, added alongside
        // TEXTS's paragraphStart/paragraphEnd fields on
        // feat/chunk-rail-and-citations), so strip those down rather than
        // leak paragraph-range fields into this entry's shape.
        .map((t) => ({ title: t.title, year: t.year }))
      if (texts.length === 0) continue
      entries.push({ workId, title: work.title, year: work.year, texts })
      continue
    }

    if (!range || (work.year >= range.start && work.year <= range.end)) {
      entries.push({ workId, title: work.title, year: work.year })
    }
  }
  return entries
}
