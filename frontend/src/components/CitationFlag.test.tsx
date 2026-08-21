import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CitationFlag } from './CitationFlag'

describe('CitationFlag', () => {
  it('renders nothing when there are no unknown citations', () => {
    const { container } = render(<CitationFlag unknownCitations={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the flag naming the unresolved citation when present', () => {
    render(<CitationFlag unknownCitations={['1907_EC_c999']} />)
    expect(screen.getByText(/1907_EC_c999/)).toBeInTheDocument()
  })
})
