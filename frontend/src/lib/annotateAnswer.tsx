import type { ReactNode } from 'react'
import type { ClaimVerdictOut } from '../api/types'

// Wraps unsupported claims in a highlight span. `claim.statement` (the
// faithfulness judge's RAGAS-style paraphrase — pronouns resolved, sentences
// split) is *not* used for locating the span: it's a rewrite, essentially
// never a literal substring of the answer. `claim.quote` is a separate,
// backend-validated verbatim span of the answer (src/generation/
// faithfulness.py:_ground_quote_in_answer) — matching against it directly
// (case-insensitive, as a defensive fallback for any residual case drift)
// is what actually finds highlightable ranges. A claim with no valid quote
// (judge failed to ground it) simply isn't highlighted.
export function annotateAnswer(text: string, claims: ClaimVerdictOut[]): ReactNode[] {
  const unsupported = claims
    .filter((c): c is ClaimVerdictOut & { quote: string } => !c.supported && !!c.quote?.trim())
    .sort((a, b) => b.quote.length - a.quote.length)

  type Range = { start: number; end: number }
  const ranges: Range[] = []
  for (const claim of unsupported) {
    const idx = text.toLowerCase().indexOf(claim.quote.toLowerCase())
    if (idx === -1) continue
    const end = idx + claim.quote.length
    const overlaps = ranges.some((r) => idx < r.end && end > r.start)
    if (!overlaps) ranges.push({ start: idx, end })
  }
  ranges.sort((a, b) => a.start - b.start)

  if (ranges.length === 0) return [text]

  const nodes: ReactNode[] = []
  let cursor = 0
  ranges.forEach((range, i) => {
    if (range.start > cursor) nodes.push(text.slice(cursor, range.start))
    nodes.push(
      <span
        key={i}
        style={{
          background: 'var(--gray-dark-bg)',
          borderBottom: '1.5px solid var(--gray-dark)',
        }}
      >
        {text.slice(range.start, range.end)}
      </span>,
    )
    cursor = range.end
  })
  if (cursor < text.length) nodes.push(text.slice(cursor))
  return nodes
}
