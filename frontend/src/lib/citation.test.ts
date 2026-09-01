import { describe, expect, it } from 'vitest'
import { formatCitation } from './citation'
import type { ChunkResult, PageRef } from '../api/types'

const EMPTY_PAGE: PageRef = { number: null, display: '' }

function chunk(overrides: Partial<ChunkResult>): ChunkResult {
  return {
    chunk_id: 'test_c1',
    work_id: '1907_EC',
    section_path: '',
    paragraph_ids: [],
    page_start: EMPTY_PAGE,
    page_end: EMPTY_PAGE,
    text: 'Texte.',
    score: 0.5,
    ...overrides,
  }
}

describe('formatCitation — non-anthology work', () => {
  it('formats as "{title} ({year}), paragraphe {n}"', () => {
    const c = chunk({ work_id: '1907_EC', paragraph_ids: ['1907_EC_p5'] })
    expect(formatCitation(c)).toBe("L'Évolution créatrice (1907), paragraphe 5")
  })
})

describe('formatCitation — anthology work, text-level data resolved', () => {
  it('formats as "{work} ({work_year}) — {text} ({text_year}), paragraphe {n}"', () => {
    // Paragraph 160 falls inside "L'effort intellectuel" (1902, range 153-203)
    // within 1919_ES (src/works.py's TEXTS).
    const c = chunk({ work_id: '1919_ES', paragraph_ids: ['1919_ES_p160'] })
    expect(formatCitation(c)).toBe(
      "L'énergie spirituelle (1919) — L'effort intellectuel (1902), paragraphe 160",
    )
  })

  it('resolves a different text for a paragraph in a different range of the same work', () => {
    // Paragraph 10 falls inside "La conscience et la vie" (1911, range 1-27).
    const c = chunk({ work_id: '1919_ES', paragraph_ids: ['1919_ES_p10'] })
    expect(formatCitation(c)).toBe(
      "L'énergie spirituelle (1919) — La conscience et la vie (1911), paragraphe 10",
    )
  })
})

describe('formatCitation — anthology work, front-matter fallback (no covering text)', () => {
  it('falls back to the non-anthology format, with no text-level fields leaking in', () => {
    // Paragraph 231 is past 1919_ES's last recorded text range (204-230),
    // i.e. back matter with no individually-dated text covering it.
    const c = chunk({ work_id: '1919_ES', paragraph_ids: ['1919_ES_p231'] })
    const result = formatCitation(c)
    expect(result).toBe("L'énergie spirituelle (1919), paragraphe 231")
    expect(result).not.toContain('—')
  })

  it('also falls back for a paragraph index below every recorded text range (front matter)', () => {
    // 1934_PM's first text starts at paragraph 4 — 1-3 is front matter.
    const c = chunk({ work_id: '1934_PM', paragraph_ids: ['1934_PM_p2'] })
    const result = formatCitation(c)
    expect(result).toBe('La Pensée et le Mouvant (1934), paragraphe 2')
    expect(result).not.toContain('—')
  })
})

describe('formatCitation — edge cases', () => {
  it('omits the paragraph clause entirely when paragraph_ids is empty', () => {
    const c = chunk({ work_id: '1907_EC', paragraph_ids: [] })
    expect(formatCitation(c)).toBe("L'Évolution créatrice (1907)")
  })

  it('falls back to the bare work_id, no year, for a work_id outside the known 8', () => {
    const c = chunk({ work_id: 'UNKNOWN_WORK', paragraph_ids: ['UNKNOWN_WORK_p1'] })
    expect(formatCitation(c)).toBe('UNKNOWN_WORK, paragraphe 1')
  })
})
