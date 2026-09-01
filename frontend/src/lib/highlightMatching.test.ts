import { describe, expect, it } from 'vitest'
import { findHighlightRanges } from './highlightMatching'
import type { ClaimVerdictOut } from '../api/types'

function claim(overrides: Partial<ClaimVerdictOut>): ClaimVerdictOut {
  return { statement: 'a paraphrased statement', supported: false, reason: 'r', quote: null, ...overrides }
}

describe('findHighlightRanges', () => {
  it('finds the verbatim quote, not the paraphrased statement', () => {
    const text = 'Bergson a rencontré Einstein en 1922.'
    const claims = [claim({ statement: 'Einstein and Bergson met in 1922', quote: 'rencontré Einstein en 1922' })]
    const ranges = findHighlightRanges(text, claims)
    expect(ranges).toHaveLength(1)
    expect(text.slice(ranges[0].start, ranges[0].end)).toBe('rencontré Einstein en 1922')
  })

  it('returns no range when the claim has no grounded quote', () => {
    const text = 'Bergson a rencontré Einstein en 1922.'
    const claims = [claim({ quote: null })]
    expect(findHighlightRanges(text, claims)).toHaveLength(0)
  })

  it('returns no range when the quote is absent from the answer', () => {
    const text = 'Bergson a rencontré Einstein en 1922.'
    const claims = [claim({ quote: 'une citation qui ne figure pas dans le texte' })]
    expect(findHighlightRanges(text, claims)).toHaveLength(0)
  })

  it('ignores supported claims', () => {
    const text = 'Bergson a rencontré Einstein en 1922.'
    const claims = [claim({ supported: true, quote: 'rencontré Einstein en 1922' })]
    expect(findHighlightRanges(text, claims)).toHaveLength(0)
  })

  it('matches case-insensitively', () => {
    const text = 'Bergson a rencontré EINSTEIN en 1922.'
    const claims = [claim({ quote: 'einstein en 1922' })]
    const ranges = findHighlightRanges(text, claims)
    expect(text.slice(ranges[0].start, ranges[0].end)).toBe('EINSTEIN en 1922')
  })

  it('drops overlapping ranges, keeping the longer quote', () => {
    const text = 'Bergson a rencontré Einstein en 1922 à Paris.'
    const claims = [
      claim({ quote: 'Einstein en 1922' }),
      claim({ quote: 'rencontré Einstein en 1922 à Paris' }),
    ]
    const ranges = findHighlightRanges(text, claims)
    expect(ranges).toHaveLength(1)
    expect(text.slice(ranges[0].start, ranges[0].end)).toBe('rencontré Einstein en 1922 à Paris')
  })
})
