import type { RetrievalConfidenceTier } from '../api/types'

const TIER_ORDER: RetrievalConfidenceTier[] = ['très faible', 'faible', 'moyenne', 'élevée']

// Blue reads as a positive/strong signal — reserved for the two confident
// tiers. The two low tiers use gray-dark instead, so a weak result never
// reads as reassuring (docs/ROADMAP.md, Sprint 8, Screen 3).
const CONFIDENT_TIERS: RetrievalConfidenceTier[] = ['moyenne', 'élevée']

export function ConfidenceGauge({ tier }: { tier: RetrievalConfidenceTier }) {
  const filled = TIER_ORDER.indexOf(tier) + 1
  const fillColor = CONFIDENT_TIERS.includes(tier) ? 'var(--blue)' : 'var(--gray-dark)'

  return (
    <div className="flex items-center gap-3 pb-3" style={{ borderBottom: '0.5px solid var(--hairline)' }}>
      <span className="text-xs" style={{ color: 'var(--ink-2)' }}>
        Confiance du retrieval
      </span>
      <div className="flex gap-[2px]" role="img" aria-label={`Confiance : ${tier}`}>
        {TIER_ORDER.map((t, i) => (
          <span
            key={t}
            className="h-[5px] w-[12px] rounded-[2px]"
            style={{ background: i < filled ? fillColor : 'var(--hairline)' }}
          />
        ))}
      </div>
      <span className="text-xs font-medium" style={{ color: 'var(--ink)' }}>
        {tier}
      </span>
    </div>
  )
}
