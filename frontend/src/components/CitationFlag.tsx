import { IconAlertTriangle } from '@tabler/icons-react'

// Only rendered if Layer 1 (the structural check) flags something — nothing
// at all when citations and titles check out, no success state
// (docs/ROADMAP.md, Sprint 8, Screen 3).
export function CitationFlag({
  unknownCitations,
  fabricatedTitles = [],
}: {
  unknownCitations: string[]
  fabricatedTitles?: string[]
}) {
  if (unknownCitations.length === 0 && fabricatedTitles.length === 0) return null

  const citationMessage =
    unknownCitations.length === 0
      ? null
      : unknownCitations.length === 1
        ? `La citation [${unknownCitations[0]}] ne correspond à aucun passage fourni.`
        : `Les citations ${unknownCitations.map((c) => `[${c}]`).join(', ')} ne correspondent à aucun passage fourni.`

  const titleMessage =
    fabricatedTitles.length === 0
      ? null
      : fabricatedTitles.length === 1
        ? `Le titre « ${fabricatedTitles[0]} » ne correspond à aucune œuvre du corpus.`
        : `Les titres ${fabricatedTitles.map((t) => `« ${t} »`).join(', ')} ne correspondent à aucune œuvre du corpus.`

  return (
    <div
      className="mb-3 flex items-start gap-2 rounded-md p-3 text-sm"
      style={{ background: 'var(--gray-dark-bg)', color: 'var(--gray-dark)' }}
    >
      <IconAlertTriangle size={16} className="mt-0.5 shrink-0" />
      <span>
        {citationMessage}
        {citationMessage && titleMessage && ' '}
        {titleMessage}
      </span>
    </div>
  )
}
