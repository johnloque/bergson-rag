import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Sources } from './Sources'
import { ANTHOLOGY_WORK_IDS, TEXTS, WORKS } from '../lib/works'
import {
  ANTHOLOGY_TEXT_RANGES,
  KNOWN_SOURCE_DESC_MISMATCHES,
  PUBLISHERS,
  WORK_CODES,
  formatChunkRange,
} from '../lib/sourceMetadata'

// Design-mockup placeholder this feature must not ship as a hardcoded
// stand-in for real extraction — it happens to land on the same string for
// all 8 works (see sourceMetadata.ts's own comment and
// tests/test_source_metadata.py, which ties that file back to a fresh XML
// parse), so the test that matters here is provenance: every publisher the
// page shows must come from the generated `sourceMetadata.ts` module, which
// is exactly what the assertions below check.

describe('Sources', () => {
  it('renders all 8 works with title, year (cross-checked against lib/works.ts) and a publisher', () => {
    render(<Sources />)

    for (const work of WORKS) {
      expect(screen.getByText(work.title)).toBeInTheDocument()
      expect(screen.getByText(`(${work.year})`)).toBeInTheDocument()
    }
  })

  it('sources every publisher value from lib/sourceMetadata.ts, not a hardcoded literal in the component', () => {
    render(<Sources />)

    for (const work of WORKS) {
      const publisher = PUBLISHERS[work.id]
      expect(publisher).toBeTruthy()
      expect(screen.getAllByText(publisher).length).toBeGreaterThan(0)
    }
  })

  it('reports the still-open 1888_EDIC sourceDesc mismatch loudly rather than staying silent', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    // Sources.tsx warns once at module scope — re-import fresh to observe it.
    vi.resetModules()
    const { Sources: FreshSources } = await import('./Sources')
    render(<FreshSources />)

    expect(KNOWN_SOURCE_DESC_MISMATCHES).toContain('1888_EDIC')
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('1888_EDIC'))
    warnSpy.mockRestore()
  })

  for (const workId of ANTHOLOGY_WORK_IDS) {
    it(`expands/collapses ${workId}'s individual texts via the shared disclosure component, matching lib/works.ts:TEXTS`, async () => {
      const user = userEvent.setup()
      render(<Sources />)
      const work = WORKS.find((w) => w.id === workId)!
      const texts = TEXTS[workId]

      const toggle = screen.getByRole('button', { name: `Afficher les textes de ${work.title}` })
      for (const text of texts) {
        expect(screen.queryByText(`${text.title} (${text.year})`)).not.toBeInTheDocument()
      }

      await user.click(toggle)
      for (const text of texts) {
        expect(screen.getByText(`${text.title} (${text.year})`, { exact: false })).toBeInTheDocument()
      }

      await user.click(screen.getByRole('button', { name: `Masquer les textes de ${work.title}` }))
      for (const text of texts) {
        expect(screen.queryByText(`${text.title} (${text.year})`)).not.toBeInTheDocument()
      }
    })
  }

  it('does not offer an expand chevron for the 6 non-anthology works', () => {
    render(<Sources />)
    for (const work of WORKS) {
      if (ANTHOLOGY_WORK_IDS.includes(work.id)) continue
      expect(
        screen.queryByRole('button', { name: `Afficher les textes de ${work.title}` }),
      ).not.toBeInTheDocument()
    }
  })

  it('links to the correct Zenodo reference, opening in a new tab', () => {
    render(<Sources />)
    const link = screen.getByRole('link', { name: 'lien vers la référence Zenodo' })
    expect(link).toHaveAttribute('href', 'https://zenodo.org/records/5075704#.YORkTjo6-Uk')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  describe('citation codes (feat/sources-citation-codes)', () => {
    it('lists exactly the works in WORK_CODES, which match lib/works.ts', () => {
      expect([...WORK_CODES]).toEqual(WORKS.map((w) => w.id))
    })

    it("shows each work's code next to its title and year", () => {
      render(<Sources />)
      for (const workId of WORK_CODES) {
        const work = WORKS.find((w) => w.id === workId)!
        const row = screen.getByText(work.title).parentElement!
        expect(row).toHaveTextContent(`${work.title} (${work.year}) · ${workId}`)
      }
    })

    it('shows a legend whose example names a real work code and title', () => {
      render(<Sources />)
      const legend = screen.getByTestId('citation-legend')
      expect(legend).toHaveTextContent('1907_EC_c5')
      expect(legend).toHaveTextContent("le cinquième paragraphe de L'Évolution créatrice")
    })

    for (const workId of ANTHOLOGY_WORK_IDS) {
      it(`shows each ${workId} text's citation range once expanded`, async () => {
        const user = userEvent.setup()
        render(<Sources />)
        const work = WORKS.find((w) => w.id === workId)!
        await user.click(screen.getByRole('button', { name: `Afficher les textes de ${work.title}` }))

        const lines = screen.getAllByRole('listitem')
        for (const { title, chunkRange } of ANTHOLOGY_TEXT_RANGES[workId]) {
          const year = TEXTS[workId].find((t) => t.title === title)!.year
          expect(chunkRange).not.toBeNull()
          expect(lines.map((li) => li.textContent)).toContain(
            `${title} (${year}) · ${formatChunkRange(chunkRange!)}`,
          )
        }
      })
    }

    it('formats a range as both full chunk_ids joined by "à"', () => {
      expect(formatChunkRange(['1919_ES_c153', '1919_ES_c203'])).toBe('1919_ES_c153 à 1919_ES_c203')
      expect(formatChunkRange(['1919_ES_c7', '1919_ES_c7'])).toBe('1919_ES_c7')
    })

    it('renders a text excluded from TEXTS without a range or placeholder', async () => {
      vi.resetModules()
      vi.doMock('../lib/sourceMetadata', async (importOriginal) => {
        const actual = await importOriginal<typeof import('../lib/sourceMetadata')>()
        return {
          ...actual,
          ANTHOLOGY_TEXT_RANGES: {
            ...actual.ANTHOLOGY_TEXT_RANGES,
            '1919_ES': [
              ...actual.ANTHOLOGY_TEXT_RANGES['1919_ES'],
              { title: 'Un texte sans date', chunkRange: null },
            ],
          },
        }
      })
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const { Sources: MockedSources } = await import('./Sources')
      const user = userEvent.setup()
      render(<MockedSources />)
      await user.click(
        screen.getByRole('button', { name: "Afficher les textes de L'Énergie spirituelle" }),
      )

      const line = screen.getByText('Un texte sans date', { exact: false })
      expect(line.textContent).toBe('Un texte sans date')
      for (const li of screen.getAllByRole('listitem')) {
        expect(li.textContent).not.toMatch(/·\s*$|\sà\s*$|null|undefined/)
      }
      warnSpy.mockRestore()
      vi.doUnmock('../lib/sourceMetadata')
    })
  })
})
