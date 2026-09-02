import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PositionFilmstrip } from './PositionFilmstrip'
import { formatCitation } from '../lib/citation'
import { focusedChunkFromResult } from '../lib/focusedChunk'
import type { ChunkNeighborSummary, ChunkResult } from '../api/types'
import type { FocusedChunk } from '../lib/focusedChunk'

const EMPTY_PAGE = { number: null, display: '' }

function chunkResult(chunkId: string): ChunkResult {
  return {
    chunk_id: chunkId,
    work_id: '1907_EC',
    section_path: '',
    paragraph_ids: ['1907_EC_p5'],
    page_start: EMPTY_PAGE,
    page_end: EMPTY_PAGE,
    text: 'Texte actuel.',
    score: 0.7,
  }
}

function neighborSummary(chunkId: string, paragraph: string): ChunkNeighborSummary {
  return {
    chunk_id: chunkId,
    work_id: '1907_EC',
    section_id: '1907_EC_s1',
    section_path: '',
    paragraph_ids: [paragraph],
    page_start: EMPTY_PAGE,
    page_end: EMPTY_PAGE,
    text: 'Texte voisin.',
  }
}

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}

afterEach(() => {
  vi.restoreAllMocks()
})

// Anchors default to the focused chunk itself — treats it as the
// originally-retrieved chunk (offset 0), so a resolved previous/next cell
// one paragraph away shows "-1"/"+1".
function renderFilmstrip(
  focused: FocusedChunk,
  onSelect: (chunk: ChunkNeighborSummary) => void,
  anchors: ChunkResult[] = [chunkResult(focused.chunk_id)],
) {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <PositionFilmstrip focusedChunk={focused} anchors={anchors} onSelect={onSelect} />
    </QueryClientProvider>,
  )
}

// docs/ROADMAP.md, Sprint 12 `feat/chunk-neighbor-expansion`, Screen 4's
// position filmstrip — fetches GET /chunks/{focused}/neighbors and renders
// three cells. Never shows full chunk text (only a compact citation), and a
// null neighbor still renders its own disabled cell rather than
// disappearing.
describe('PositionFilmstrip', () => {
  it('renders previous/current/next once neighbors resolve, showing citations only (no chunk text)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ previous: neighborSummary('1907_EC_c4', '1907_EC_p4'), next: neighborSummary('1907_EC_c6', '1907_EC_p6') }),
      ),
    )
    const focused = focusedChunkFromResult(chunkResult('1907_EC_c5'))
    renderFilmstrip(focused, vi.fn())

    await waitFor(() =>
      expect(screen.getByTestId('filmstrip-cell-previous')).toHaveTextContent(
        formatCitation(neighborSummary('1907_EC_c4', '1907_EC_p4')),
      ),
    )
    expect(screen.getByTestId('filmstrip-cell-next')).toHaveTextContent(
      formatCitation(neighborSummary('1907_EC_c6', '1907_EC_p6')),
    )
    expect(screen.getByTestId('filmstrip-cell-current')).toHaveTextContent(formatCitation(focused))
    // Compact selector: the focused chunk's own body text never renders here.
    expect(screen.queryByText('Texte actuel.')).not.toBeInTheDocument()
    expect(screen.queryByText('Texte voisin.')).not.toBeInTheDocument()
  })

  // docs/ROADMAP.md, Sprint 12 refinement: each cell shows its distance,
  // in paragraphs, from the nearest originally-retrieved anchor —
  // lib/chunkOffset.ts, not tracked through navigation.
  it('labels each cell with its distance from the originally-retrieved anchor', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ previous: neighborSummary('1907_EC_c4', '1907_EC_p4'), next: neighborSummary('1907_EC_c6', '1907_EC_p6') }),
      ),
    )
    const focused = focusedChunkFromResult(chunkResult('1907_EC_c5'))
    renderFilmstrip(focused, vi.fn(), [chunkResult('1907_EC_c5')])

    await waitFor(() => expect(screen.getByTestId('filmstrip-cell-previous-offset')).toHaveTextContent('-1'))
    expect(screen.getByTestId('filmstrip-cell-current-offset')).toHaveTextContent('0')
    expect(screen.getByTestId('filmstrip-cell-next-offset')).toHaveTextContent('+1')
  })

  // QA regression: when the focused chunk is itself a retrieved anchor
  // (e.g. rank 3) and its *previous* neighbor happens to ALSO be a
  // retrieved anchor (rank-adjacent, but a different rank), each cell used
  // to independently look up its own nearest anchor — the previous cell
  // then found itself as its own nearest anchor (distance 0) instead of
  // being positioned relative to the chunk actually being inspected, so
  // both cells showed "0". previous/next must always be exactly
  // currentOffset ∓ 1.
  it('positions the previous cell relative to the focused chunk even when the previous chunk is itself a retrieved anchor', async () => {
    function pmChunkResult(chunkId: string, paragraph: number): ChunkResult {
      return {
        chunk_id: chunkId,
        work_id: '1934_PM',
        section_path: '',
        paragraph_ids: [`1934_PM_p${paragraph}`],
        page_start: EMPTY_PAGE,
        page_end: EMPTY_PAGE,
        text: 'Texte.',
        score: 0.7,
      }
    }
    const c67 = pmChunkResult('1934_PM_c67', 67)
    const c68 = pmChunkResult('1934_PM_c68', 68)
    const previousNeighbor: ChunkNeighborSummary = {
      chunk_id: c67.chunk_id,
      work_id: c67.work_id,
      section_id: '1934_PM_s1',
      section_path: '',
      paragraph_ids: c67.paragraph_ids,
      page_start: EMPTY_PAGE,
      page_end: EMPTY_PAGE,
      text: c67.text,
    }
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ previous: previousNeighbor, next: null })))
    const focused = focusedChunkFromResult(c68)
    // Both c67 and c68 are retrieved anchors, ranked 3 apart — the exact
    // reported scenario (a rank-3 chunk whose textual predecessor is also
    // in the retrieved set, just at a different rank).
    renderFilmstrip(focused, vi.fn(), [c67, pmChunkResult('1934_PM_c50', 50), c68])

    await waitFor(() => expect(screen.getByTestId('filmstrip-cell-previous-offset')).toHaveTextContent('-1'))
    expect(screen.getByTestId('filmstrip-cell-current-offset')).toHaveTextContent('0')
  })

  it('renders a disabled, empty cell (not nothing) for a null neighbor — a section boundary', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ previous: null, next: neighborSummary('1907_EC_c6', '1907_EC_p6') })))
    const focused = focusedChunkFromResult(chunkResult('1907_EC_c5'))
    renderFilmstrip(focused, vi.fn())

    await waitFor(() =>
      expect(screen.getByTestId('filmstrip-cell-previous')).toHaveTextContent('Début de section'),
    )
    expect(screen.getByTestId('filmstrip-cell-previous')).toBeDisabled()
  })

  it('clicking a resolved neighbor cell calls onSelect with that neighbor', async () => {
    const nextNeighbor = neighborSummary('1907_EC_c6', '1907_EC_p6')
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ previous: null, next: nextNeighbor })))
    const onSelect = vi.fn()
    const user = userEvent.setup()
    const focused = focusedChunkFromResult(chunkResult('1907_EC_c5'))
    renderFilmstrip(focused, onSelect)

    await waitFor(() => expect(screen.getByTestId('filmstrip-cell-next')).not.toBeDisabled())
    await user.click(screen.getByTestId('filmstrip-cell-next'))

    expect(onSelect).toHaveBeenCalledWith(nextNeighbor)
  })

  it('re-fetches neighbors when the focused chunk changes (filmstrip re-centers)', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      expect(url).toContain('/chunks/')
      return jsonResponse({ previous: null, next: null })
    })
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = new QueryClient()
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <PositionFilmstrip
          focusedChunk={focusedChunkFromResult(chunkResult('1907_EC_c5'))}
          anchors={[chunkResult('1907_EC_c5')]}
          onSelect={vi.fn()}
        />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock.mock.calls[0][0]).toContain('/chunks/1907_EC_c5/neighbors')

    rerender(
      <QueryClientProvider client={queryClient}>
        <PositionFilmstrip
          focusedChunk={focusedChunkFromResult(chunkResult('1907_EC_c6'))}
          anchors={[chunkResult('1907_EC_c5')]}
          onSelect={vi.fn()}
        />
      </QueryClientProvider>,
    )

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(fetchMock.mock.calls[1][0]).toContain('/chunks/1907_EC_c6/neighbors')
  })
})
