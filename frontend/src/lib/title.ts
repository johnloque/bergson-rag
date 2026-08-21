// Auto-generated sidebar titles derive from a turn's first query
// (docs/ROADMAP.md, Sprint 8, Screen 2) — truncate at a word boundary,
// never mid-word.
export function deriveTitle(query: string, maxLen = 42): string {
  const trimmed = query.trim()
  if (trimmed.length <= maxLen) return trimmed
  const slice = trimmed.slice(0, maxLen)
  const lastSpace = slice.lastIndexOf(' ')
  const cut = lastSpace > maxLen * 0.4 ? slice.slice(0, lastSpace) : slice
  return `${cut.trimEnd()}…`
}
