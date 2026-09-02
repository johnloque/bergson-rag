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

function renderFilmstrip(focused: FocusedChunk, onSelect: (chunk: ChunkNeighborSummary) => void) {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <PositionFilmstrip focusedChunk={focused} onSelect={onSelect} />
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
        <PositionFilmstrip focusedChunk={focusedChunkFromResult(chunkResult('1907_EC_c5'))} onSelect={vi.fn()} />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock.mock.calls[0][0]).toContain('/chunks/1907_EC_c5/neighbors')

    rerender(
      <QueryClientProvider client={queryClient}>
        <PositionFilmstrip focusedChunk={focusedChunkFromResult(chunkResult('1907_EC_c6'))} onSelect={vi.fn()} />
      </QueryClientProvider>,
    )

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(fetchMock.mock.calls[1][0]).toContain('/chunks/1907_EC_c6/neighbors')
  })
})
