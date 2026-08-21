import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { annotateAnswer } from './annotateAnswer'
import type { ClaimVerdictOut } from '../api/types'

function claim(overrides: Partial<ClaimVerdictOut>): ClaimVerdictOut {
  return { statement: 'a paraphrased statement', supported: false, reason: 'r', quote: null, ...overrides }
}

describe('annotateAnswer', () => {
  it('highlights the verbatim quote, not the paraphrased statement', () => {
    const text = 'Bergson a rencontré Einstein en 1922.'
    const claims = [claim({ statement: 'Einstein and Bergson met in 1922', quote: 'rencontré Einstein en 1922' })]
    const { container } = render(<div>{annotateAnswer(text, claims)}</div>)
    const span = container.querySelector('span')
    expect(span?.textContent).toBe('rencontré Einstein en 1922')
  })

  it('renders plain text with no highlight when the claim has no grounded quote', () => {
    const text = 'Bergson a rencontré Einstein en 1922.'
    const claims = [claim({ quote: null })]
    const { container } = render(<div>{annotateAnswer(text, claims)}</div>)
    expect(container.querySelector('span')).toBeNull()
    expect(container.textContent).toBe(text)
  })

  it('renders plain text with no highlight when the quote is absent from the answer', () => {
    const text = 'Bergson a rencontré Einstein en 1922.'
    const claims = [claim({ quote: 'une citation qui ne figure pas dans le texte' })]
    const { container } = render(<div>{annotateAnswer(text, claims)}</div>)
    expect(container.querySelector('span')).toBeNull()
  })

  it('ignores supported claims', () => {
    const text = 'Bergson a rencontré Einstein en 1922.'
    const claims = [claim({ supported: true, quote: 'rencontré Einstein en 1922' })]
    const { container } = render(<div>{annotateAnswer(text, claims)}</div>)
    expect(container.querySelector('span')).toBeNull()
  })

  it('matches case-insensitively', () => {
    const text = 'Bergson a rencontré EINSTEIN en 1922.'
    const claims = [claim({ quote: 'einstein en 1922' })]
    const { container } = render(<div>{annotateAnswer(text, claims)}</div>)
    expect(container.querySelector('span')?.textContent).toBe('EINSTEIN en 1922')
  })

  it('drops overlapping ranges, keeping the longer quote', () => {
    const text = 'Bergson a rencontré Einstein en 1922 à Paris.'
    const claims = [
      claim({ quote: 'Einstein en 1922' }),
      claim({ quote: 'rencontré Einstein en 1922 à Paris' }),
    ]
    const { container } = render(<div>{annotateAnswer(text, claims)}</div>)
    const spans = container.querySelectorAll('span')
    expect(spans).toHaveLength(1)
    expect(spans[0].textContent).toBe('rencontré Einstein en 1922 à Paris')
  })
})
