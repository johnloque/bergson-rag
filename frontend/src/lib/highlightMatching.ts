import type { ClaimVerdictOut } from '../api/types'

export interface HighlightRange {
  start: number
  end: number
}

// Finds the non-overlapping, verbatim-quote character ranges inside `text`
// that a faithfulness judge flagged as unsupported — the shared primitive
// behind both plain-text highlighting and the markdown-aware rehype plugin
// (lib/highlightPlugin.ts), so the two rendering paths can never disagree
// on what counts as a match.
//
// `claim.statement` (the faithfulness judge's RAGAS-style paraphrase —
// pronouns resolved, sentences split) is *not* used for locating the span:
// it's a rewrite, essentially never a literal substring of the answer.
// `claim.quote` is a separate, backend-validated verbatim span of the
// answer (src/generation/faithfulness.py:_ground_quote_in_answer) — matching
// against it directly (case-insensitive, as a defensive fallback for any
// residual case drift) is what actually finds highlightable ranges. A claim
// with no valid quote (judge failed to ground it) simply isn't matched.
//
// Longest-quote-first, drop-on-overlap: when two claims' quotes overlap in
// `text`, the longer one wins outright rather than splitting the
// difference — arbitrary but deterministic, and avoids a shorter quote
// nested entirely inside a longer one producing two overlapping spans.
export function findHighlightRanges(text: string, claims: ClaimVerdictOut[]): HighlightRange[] {
  const unsupported = claims
    .filter((c): c is ClaimVerdictOut & { quote: string } => !c.supported && !!c.quote?.trim())
    .sort((a, b) => b.quote.length - a.quote.length)

  const ranges: HighlightRange[] = []
  for (const claim of unsupported) {
    const idx = text.toLowerCase().indexOf(claim.quote.toLowerCase())
    if (idx === -1) continue
    const end = idx + claim.quote.length
    const overlaps = ranges.some((r) => idx < r.end && end > r.start)
    if (!overlaps) ranges.push({ start: idx, end })
  }
  ranges.sort((a, b) => a.start - b.start)
  return ranges
}
