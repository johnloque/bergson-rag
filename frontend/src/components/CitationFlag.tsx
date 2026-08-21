import { IconAlertTriangle } from '@tabler/icons-react'

// Only rendered if Layer 1 (the structural check) flags something — nothing
// at all when citations check out, no success state (docs/ROADMAP.md,
// Sprint 8, Screen 3).
export function CitationFlag({ unknownCitations }: { unknownCitations: string[] }) {
  if (unknownCitations.length === 0) return null

  const message =
    unknownCitations.length === 1
      ? `La citation [${unknownCitations[0]}] ne correspond à aucun passage fourni.`
      : `Les citations ${unknownCitations.map((c) => `[${c}]`).join(', ')} ne correspondent à aucun passage fourni.`

  return (
    <div
      className="mb-3 flex items-start gap-2 rounded-md p-3 text-sm"
      style={{ background: 'var(--gray-dark-bg)', color: 'var(--gray-dark)' }}
    >
      <IconAlertTriangle size={16} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  )
}
