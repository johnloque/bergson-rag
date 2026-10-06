import { describe, expect, it } from 'vitest'
import { sourceOffsets } from './segmentPlugin'

describe('sourceOffsets', () => {
  it('maps a verbatim text leaf one to one', () => {
    expect(sourceOffsets('abc', 'xxabcxx', 2, 5)).toEqual([2, 3, 4])
  })

  it('skips source characters the parser dropped (escape, continuation indent)', () => {
    const source = 'a \\* b\n  c'
    // Rendered: escape removed, indent removed.
    expect(sourceOffsets('a * b\nc', source, 0, source.length)).toEqual([0, 1, 3, 4, 5, 6, 9])
  })
})
