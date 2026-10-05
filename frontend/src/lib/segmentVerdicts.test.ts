import { describe, expect, it } from 'vitest'
import type { ClaimVerdictOut } from '../api/types'
import { groupClaimsBySegment, segmentStatus } from './segmentVerdicts'

function claim(supported: boolean | null, segment_id: number | null = 0): ClaimVerdictOut {
  return { statement: 's', supported, reason: supported === null ? null : 'r', segment_id }
}

describe('segmentStatus', () => {
  it('is unsupported as soon as one claim is', () => {
    expect(segmentStatus([claim(true), claim(false), claim(null)])).toBe('unsupported')
  })
  it('is supported only when every claim is', () => {
    expect(segmentStatus([claim(true), claim(true)])).toBe('supported')
  })
  it('is unevaluated when no claim is unsupported but one is not evaluated', () => {
    expect(segmentStatus([claim(true), claim(null)])).toBe('unevaluated')
  })
  it('has no status without claims', () => {
    expect(segmentStatus([])).toBeNull()
  })
})

describe('groupClaimsBySegment', () => {
  it('groups claims in order and skips those without a segment (pre-segment evaluations)', () => {
    const a = claim(true, 1)
    const b = claim(false, 0)
    const c = claim(true, 1)
    const grouped = groupClaimsBySegment([a, b, c, claim(true, null)])
    expect(grouped.get(1)).toEqual([a, c])
    expect(grouped.get(0)).toEqual([b])
    expect(grouped.size).toBe(2)
  })
})
