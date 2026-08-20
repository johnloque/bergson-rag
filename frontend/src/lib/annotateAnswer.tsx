import type { ReactNode } from 'react'
import type { ClaimVerdictOut } from '../api/types'

// Wraps unsupported claims in a highlight span. Claim statements come from
// the faithfulness judge (RAGAS-style claim extraction) and are not
// guaranteed to be a literal substring of the answer — this is a
// best-effort literal, case-insensitive match; a claim that doesn't appear
// verbatim simply isn't highlighted rather than forcing a fuzzy match.
export function annotateAnswer(text: string, claims: ClaimVerdictOut[]): ReactNode[] {
  const unsupported = claims
    .filter((c) => !c.supported && c.statement.trim().length > 0)
    .sort((a, b) => b.statement.length - a.statement.length)

  type Range = { start: number; end: number }
  const ranges: Range[] = []
  for (const claim of unsupported) {
    const idx = text.toLowerCase().indexOf(claim.statement.toLowerCase())
    if (idx === -1) continue
    const end = idx + claim.statement.length
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
