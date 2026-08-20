import type { ChunkJudgmentLabel } from '../api/types'

const STYLES: Record<ChunkJudgmentLabel, { bg: string; color: string }> = {
  pertinent: { bg: 'var(--green-bg)', color: 'var(--green)' },
  'partiellement pertinent': { bg: 'var(--amber-bg)', color: 'var(--amber)' },
  'non pertinent': { bg: 'var(--red-bg)', color: 'var(--red)' },
}

export function RelevancePill({ label }: { label: ChunkJudgmentLabel }) {
  const style = STYLES[label]
  return (
    <span
      className="inline-flex items-center rounded-full px-3 py-1 text-xs font-medium capitalize"
      style={{ background: style.bg, color: style.color }}
    >
      {label}
    </span>
  )
}
