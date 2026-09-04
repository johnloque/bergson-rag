import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Sources } from './Sources'
import { ANTHOLOGY_WORK_IDS, TEXTS, WORKS } from '../lib/works'
import { KNOWN_SOURCE_DESC_MISMATCHES, PUBLISHERS } from '../lib/sourceMetadata'

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
})
