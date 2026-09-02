import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ChunkDetail } from './ChunkDetail'
import { ChunkRail } from '../components/ChunkRail'
import { formatCitation } from '../lib/citation'
import { TurnUiProvider } from '../state/turnUi'

const EMPTY_PAGE = { number: null, display: '' }

const RETRIEVED_C1 = {
  chunk_id: '1907_EC_c1',
  rank: 0,
  work_id: '1907_EC',
  section_path: '',
  paragraph_ids: ['1907_EC_p1'],
  page_start: EMPTY_PAGE,
  page_end: EMPTY_PAGE,
  text: 'Texte du chunk retrouvé un.',
  score: 0.9,
}
const RETRIEVED_C2 = {
  ...RETRIEVED_C1,
  chunk_id: '1907_EC_c2',
  rank: 1,
  paragraph_ids: ['1907_EC_p2'],
  text: 'Texte du chunk retrouvé deux.',
  score: 0.6,
}
// A chunk that is NOT part of the retrieved set — reached only via the
// filmstrip, from 1907_EC_c1's `next`.
const NEIGHBOR_C3 = {
  chunk_id: '1907_EC_c3',
  work_id: '1907_EC',
  section_id: '1907_EC_s1',
  section_path: '',
  paragraph_ids: ['1907_EC_p3'],
  page_start: EMPTY_PAGE,
  page_end: EMPTY_PAGE,
  text: 'Texte du chunk voisin trois.',
}

const TURN_DETAIL = {
  turn_id: 1,
  conversation_id: 1,
  query: 'Une question',
  created_at: new Date().toISOString(),
  retrieved_chunks: [RETRIEVED_C1, RETRIEVED_C2],
  generations: [],
  chunk_judgments: {},
  work_ids: null,
  date_range: null,
}

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}

function stubFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.endsWith('/turns/1')) return jsonResponse(TURN_DETAIL)
      if (url.includes('/chunks/1907_EC_c1/neighbors'))
        return jsonResponse({ previous: null, next: NEIGHBOR_C3 })
      if (url.includes('/chunks/1907_EC_c2/neighbors'))
        return jsonResponse({ previous: null, next: null })
      if (url.includes('/chunks/1907_EC_c3/neighbors'))
        return jsonResponse({ previous: null, next: null })
      if (url.endsWith('/confidence-preview')) return jsonResponse({ retrieval_confidence_tier: 'moyenne' })
      throw new Error(`unexpected fetch: ${url}`)
    }),
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

function renderChunkDetail(initialChunkId = '1907_EC_c1') {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <TurnUiProvider>
        <MemoryRouter initialEntries={[`/c/1/turn/1/chunk/${initialChunkId}`]}>
          <Routes>
            <Route path="/c/:conversationId/turn/:turnId/chunk/:chunkId" element={<ChunkDetail />} />
          </Routes>
        </MemoryRouter>
      </TurnUiProvider>
    </QueryClientProvider>,
  )
}

// docs/ROADMAP.md, Sprint 12 `feat/chunk-neighbor-expansion`: Screen 4's
// master-detail restructure — a single shared detail panel driven by
// either the retrieval rail or the position filmstrip.
describe('ChunkDetail — master-detail', () => {
  it('focuses the URL-provided chunk initially, tagged as coming from the search results', async () => {
    stubFetch()
    renderChunkDetail('1907_EC_c1')

    await waitFor(() =>
      expect(screen.getByTestId('focused-chunk-citation')).toHaveTextContent(formatCitation(RETRIEVED_C1)),
    )
    expect(screen.getByTestId('focused-chunk-text')).toHaveTextContent(RETRIEVED_C1.text)
    expect(screen.getByTestId('chunk-origin-tag')).toHaveTextContent('Depuis la recherche')
  })

  it('clicking a rail card updates the shared detail panel', async () => {
    stubFetch()
    const user = userEvent.setup()
    renderChunkDetail('1907_EC_c1')
    await waitFor(() =>
      expect(screen.getByTestId('focused-chunk-citation')).toHaveTextContent(formatCitation(RETRIEVED_C1)),
    )

    const card = screen.getByTestId(`chunk-card-${RETRIEVED_C2.chunk_id}`)
    await user.click(within(card).getByText('Inspecter'))

    expect(screen.getByTestId('focused-chunk-citation')).toHaveTextContent(formatCitation(RETRIEVED_C2))
    expect(screen.getByTestId('focused-chunk-text')).toHaveTextContent(RETRIEVED_C2.text)
    expect(screen.getByTestId('chunk-origin-tag')).toHaveTextContent('Depuis la recherche')
  })

  it('clicking a filmstrip cell updates the same shared detail panel, tagged as a neighbor outside the search results', async () => {
    stubFetch()
    const user = userEvent.setup()
    renderChunkDetail('1907_EC_c1')

    await waitFor(() => expect(screen.getByTestId('filmstrip-cell-next')).toHaveTextContent(formatCitation(NEIGHBOR_C3)))
    await user.click(screen.getByTestId('filmstrip-cell-next'))

    expect(screen.getByTestId('focused-chunk-citation')).toHaveTextContent(formatCitation(NEIGHBOR_C3))
    expect(screen.getByTestId('focused-chunk-text')).toHaveTextContent(NEIGHBOR_C3.text)
    expect(screen.getByTestId('chunk-origin-tag')).toHaveTextContent('Voisin — hors des résultats de recherche')
  })

  it('the detail panel renders identically (citation + text) regardless of which selector set the focus', async () => {
    stubFetch()
    const user = userEvent.setup()
    renderChunkDetail('1907_EC_c1')

    // Reach 1907_EC_c3 via the filmstrip.
    await waitFor(() => expect(screen.getByTestId('filmstrip-cell-next')).not.toBeDisabled())
    await user.click(screen.getByTestId('filmstrip-cell-next'))
    const viaFilmstripCitation = screen.getByTestId('focused-chunk-citation').textContent
    const viaFilmstripText = screen.getByTestId('focused-chunk-text').textContent

    // Same chunk, reached a different way this time: back to c1 via the
    // rail, then include+re-navigate is unnecessary — instead assert
    // clicking the rail's own c1 card reproduces c1's panel exactly as the
    // initial URL-driven focus did.
    const card = screen.getByTestId(`chunk-card-${RETRIEVED_C1.chunk_id}`)
    await user.click(within(card).getByText('Inspecter'))

    expect(screen.getByTestId('focused-chunk-citation')).toHaveTextContent(formatCitation(RETRIEVED_C1))
    expect(screen.getByTestId('focused-chunk-text')).toHaveTextContent(RETRIEVED_C1.text)
    // Sanity: the filmstrip-driven panel really did show different content.
    expect(viaFilmstripCitation).not.toEqual(screen.getByTestId('focused-chunk-citation').textContent)
    expect(viaFilmstripText).not.toEqual(screen.getByTestId('focused-chunk-text').textContent)
  })

  it('including a neighbor chunk from the detail panel appends it to the Screen 3 rail with a dashed border and the real citation', async () => {
    stubFetch()
    const user = userEvent.setup()
    const queryClient = new QueryClient()

    function Harness() {
      return (
        <QueryClientProvider client={queryClient}>
          <TurnUiProvider>
            <MemoryRouter initialEntries={['/c/1/turn/1/chunk/1907_EC_c1']}>
              <Routes>
                <Route path="/c/:conversationId/turn/:turnId/chunk/:chunkId" element={<ChunkDetail />} />
              </Routes>
            </MemoryRouter>
            {/* Simulates Screen 3's own rail, sharing the same TurnUiProvider
                instance — the real single-source-of-truth setup (App.tsx
                mounts one TurnUiProvider above the router). Its own
                MemoryRouter (ChunkRail needs router context for its
                navigate fallback) is independent of the one above — only
                the TurnUiProvider is actually shared here. */}
            <MemoryRouter>
              <ChunkRail chunks={[RETRIEVED_C1, RETRIEVED_C2]} turnId={1} conversationId={1} />
            </MemoryRouter>
          </TurnUiProvider>
        </QueryClientProvider>
      )
    }
    render(<Harness />)

    await waitFor(() => expect(screen.getByTestId('filmstrip-cell-next')).not.toBeDisabled())
    await user.click(screen.getByTestId('filmstrip-cell-next'))
    await waitFor(() => expect(screen.getByTestId('chunk-origin-tag')).toHaveTextContent('Voisin'))

    // Two "Inclure" buttons could exist (detail panel's own) — scope to the
    // detail panel column, which is the only place it renders for a
    // non-rail-origin focused chunk (the rail has no card for 1907_EC_c3
    // yet, since it isn't included).
    await user.click(screen.getByRole('button', { name: 'Inclure' }))

    // Both ChunkDetail's own top rail (Zone 1) and the simulated Screen 3
    // rail below render a card for it now — they share the same
    // TurnUiProvider, the single source of truth this feature relies on.
    const railCards = screen.getAllByTestId(`chunk-card-${NEIGHBOR_C3.chunk_id}`)
    expect(railCards).toHaveLength(2)
    for (const card of railCards) {
      expect(card).toHaveAttribute('data-origin', 'neighbor')
      expect(within(card).getByTestId('chunk-citation')).toHaveTextContent(formatCitation(NEIGHBOR_C3))
    }
    expect(screen.getAllByTestId('neighbor-rail')).toHaveLength(2)
  })
})
