interface StatusPillProps {
  tone: 'pending' | 'verifying' | 'verified' | 'failed'
}

// "Non vérifié" (gray-light) while /generate has returned but /evaluate
// hasn't been called yet; "Vérification en cours" (blue) once /evaluate is
// in flight; "Vérifié" (green) once /evaluate has resolved — the card can
// still stay collapsed (should_auto_expand false, docs/ROADMAP.md's
// anti-hallucination guardrail), but the badge must not keep reading "Non
// vérifié" once a check actually ran and is persisted. "Vérification
// indisponible" (red) when /evaluate errored (e.g. provider down) — this
// must stay distinct from "verified" since no faithfulness/confidence data
// actually exists in that case.
const TONE_STYLE = {
  pending: { bg: 'var(--gray-light-bg)', color: 'var(--gray-light)', label: 'Non vérifié' },
  verifying: { bg: 'var(--blue-bg)', color: 'var(--blue)', label: 'Vérification en cours' },
  verified: { bg: 'var(--green-bg)', color: 'var(--green)', label: 'Vérifié' },
  failed: { bg: 'var(--red-bg)', color: 'var(--red)', label: 'Vérification indisponible' },
} as const

export function StatusPill({ tone }: StatusPillProps) {
  const { bg, color, label } = TONE_STYLE[tone]
  return (
    <span
      className="inline-flex items-center rounded-full px-3 py-1 text-xs font-medium"
      style={{ background: bg, color }}
    >
      {label}
    </span>
  )
}
