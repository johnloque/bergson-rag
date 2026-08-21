import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConfidenceGauge } from './ConfidenceGauge'
import type { RetrievalConfidenceTier } from '../api/types'

describe('ConfidenceGauge', () => {
  it.each([
    ['très faible', 1, 'var(--gray-dark)'],
    ['faible', 2, 'var(--gray-dark)'],
    ['moyenne', 3, 'var(--blue)'],
    ['élevée', 4, 'var(--blue)'],
  ] as [RetrievalConfidenceTier, number, string][])(
    'tier %s fills %d segments in %s',
    (tier, filled, color) => {
      render(<ConfidenceGauge tier={tier} />)
      const gauge = screen.getByRole('img', { name: `Confiance : ${tier}` })
      const segments = gauge.querySelectorAll('span')
      expect(segments).toHaveLength(4)
      segments.forEach((seg, i) => {
        const expected = i < filled ? color : 'var(--hairline)'
        expect((seg as HTMLElement).style.background).toBe(expected)
      })
    },
  )
})
