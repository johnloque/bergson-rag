import { describe, expect, it } from 'vitest'
import { computeConsideredSources } from './retrievalScope'
import { ALL_WORK_IDS } from './works'

describe('computeConsideredSources — unknown filter (hydrated/reloaded turn)', () => {
  it('returns null when filterParams is undefined, never a guessed default', () => {
    expect(computeConsideredSources(undefined)).toBeNull()
  })
})

describe('computeConsideredSources — no filter applied', () => {
  it('lists all 8 works at whole-work granularity', () => {
    const result = computeConsideredSources({})
    expect(result).not.toBeNull()
    expect(result!.map((e) => e.workId)).toEqual(ALL_WORK_IDS)
    expect(result!.every((e) => e.texts === undefined)).toBe(true)
  })
})

describe('computeConsideredSources — work_ids narrowed', () => {
  it('lists only the allowed works, in the given order', () => {
    const result = computeConsideredSources({ work_ids: ['1900_R', '1888_EDIC'] })
    expect(result!.map((e) => e.workId)).toEqual(['1900_R', '1888_EDIC'])
  })

  it('returns an empty list for an explicit empty work_ids array', () => {
    expect(computeConsideredSources({ work_ids: [] })).toEqual([])
  })
})

describe('computeConsideredSources — "publication" mode date_range', () => {
  it('keeps only works whose publication year falls in range, anthology works included whole', () => {
    // 1919_ES publishes in 1919 -- out of this range even though one of
    // its individual texts (1902's "L'effort intellectuel") is in range;
    // publication mode never looks at the individual text years.
    const result = computeConsideredSources({ date_range: { start: 1900, end: 1913, mode: 'publication' } })
    const ids = result!.map((e) => e.workId)
    expect(ids).toContain('1900_R')
    expect(ids).toContain('1907_EC')
    expect(ids).not.toContain('1919_ES')
    expect(result!.every((e) => e.texts === undefined)).toBe(true)
  })
})

describe('computeConsideredSources — "text" mode date_range', () => {
  it('isolates a single individually-dated text when the range covers only its year', () => {
    const range = { start: 1902, end: 1902, mode: 'text' as const }
    const result = computeConsideredSources({ work_ids: ['1919_ES'], date_range: range })
    expect(result).toHaveLength(1)
    expect(result![0].workId).toBe('1919_ES')
    expect(result![0].texts).toEqual([{ title: "L'effort intellectuel", year: 1902 }])
  })

  it('distinguishes text mode from publication mode for the same range (docs/backend_api.md\'s Sprint 11 example)', () => {
    // A range covering 1919_ES's own 1919 publication year but none of its
    // individual texts' years (all 1901-1913): publication mode includes
    // the work wholesale (work-level year is in range); text mode excludes
    // it entirely (no individual dated text qualifies).
    const range = { start: 1915, end: 1919 }
    const publicationResult = computeConsideredSources({
      work_ids: ['1919_ES'],
      date_range: { ...range, mode: 'publication' },
    })
    const textResult = computeConsideredSources({ work_ids: ['1919_ES'], date_range: { ...range, mode: 'text' } })
    expect(publicationResult).toEqual([{ workId: '1919_ES', title: "L'énergie spirituelle", year: 1919 }])
    expect(textResult).toEqual([])
  })

  it('omits an anthology work entirely once none of its texts are in range', () => {
    const range = { start: 1950, end: 1960, mode: 'text' as const }
    const result = computeConsideredSources({ work_ids: ['1919_ES'], date_range: range })
    expect(result).toEqual([])
  })

  it('treats a non-anthology work at whole-work granularity even in "text" mode', () => {
    const range = { start: 1895, end: 1901, mode: 'text' as const }
    const result = computeConsideredSources({ work_ids: ['1896_MM'], date_range: range })
    expect(result).toEqual([{ workId: '1896_MM', title: 'Matière et mémoire', year: 1896 }])
  })

  it('can list multiple qualifying texts for the same anthology work', () => {
    const range = { start: 1911, end: 1913, mode: 'text' as const }
    const result = computeConsideredSources({ work_ids: ['1919_ES'], date_range: range })
    expect(result![0].texts).toEqual([
      { title: 'La conscience et la vie', year: 1911 },
      { title: "L'âme et le corps", year: 1912 },
      { title: '"Fantômes de vivants" et "recherche psychique"', year: 1913 },
    ])
  })
})
