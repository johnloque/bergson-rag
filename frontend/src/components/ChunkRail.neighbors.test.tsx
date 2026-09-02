import { useEffect } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ChunkRail } from './ChunkRail'
import { api } from '../api/client'
import { formatCitation } from '../lib/citation'
import { TurnUiProvider, useTurnUi } from '../state/turnUi'
import type { ChunkNeighborSummary, ChunkResult } from '../api/types'

const chunkA: ChunkResult = {
  chunk_id: 'W_c1',
  work_id: 'W',
  section_path: '',
  paragraph_ids: [],
  page_start: { number: null, display: '' },
  page_end: { number: null, display: '' },
  text: 'Un passage.',
  score: 0.5,
}

const NEIGHBOR: ChunkNeighborSummary = {
  chunk_id: '1907_EC_c6',
  work_id: '1907_EC',
  section_id: '1907_EC_s1',
  section_path: '',
  paragraph_ids: ['1907_EC_p6'],
  page_start: { number: null, display: '' },
  page_end: { number: null, display: '' },
  text: 'Un passage voisin.',
}

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}

afterEach(() => {
  vi.restoreAllMocks()
})

// Seeds turnUi (state/turnUi.tsx) the way a real /retrieve + a real
// neighbor-inclusion would, then renders the rail on top of it — same
// harness pattern as ChunkRail.test.tsx's renderInitializedRail.
function renderRailWithNeighbor(neighbor: ChunkNeighborSummary | null, chunks: ChunkResult[] = [chunkA]) {
  function Harness() {
    const turnUi = useTurnUi()
    useEffect(() => {
      turnUi.initTurn(
        1,
        chunks.map((c) => c.chunk_id),
      )
      if (neighbor) turnUi.toggleNeighborChunk(1, neighbor)
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
    return <ChunkRail chunks={chunks} turnId={1} conversationId={1} />
  }
  return render(
    <TurnUiProvider>
      <MemoryRouter>
        <Harness />
      </MemoryRouter>
    </TurnUiProvider>,
  )
}

// docs/ROADMAP.md, Sprint 12 `feat/chunk-neighbor-expansion`: the Screen 3
// rail extension — a chunk included via Screen 4's neighbor exploration
// must show up here too, distinct from the retrieved-candidate cards.
describe('ChunkRail — neighbor-origin cards', () => {
  it('renders a neighbor-origin card in a second, separately-titled rail below the retrieved candidates, with the real citation', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })))
    renderRailWithNeighbor(NEIGHBOR)

    expect(screen.getByText('Chunks issus de la recherche')).toBeInTheDocument()
    expect(screen.getByText('Chunks voisins ajoutés manuellement')).toBeInTheDocument()
    const neighborRail = screen.getByTestId('neighbor-rail')
    const card = within(neighborRail).getByTestId(`chunk-card-${NEIGHBOR.chunk_id}`)
    expect(card).toHaveAttribute('data-included', 'true')
    expect(card).toHaveAttribute('data-origin', 'neighbor')
    expect(within(card).getByTestId('chunk-citation')).toHaveTextContent(formatCitation(NEIGHBOR))
  })

  // docs/ROADMAP.md: no distance badge on the second rail's cards, even
  // when a same-work retrieved anchor exists to measure against — unlike
  // PositionFilmstrip's cells (always exactly ±1 from the chunk actually
  // being inspected), this rail has no reliable way to know which
  // retrieved chunk a given neighbor was actually expanded from, so a
  // "nearest anchor by paragraph distance" badge here would look precise
  // while sometimes being wrong.
  it('never shows a distance badge on a neighbor-origin card', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })))
    const retrieved: ChunkResult = {
      chunk_id: '1907_EC_c5',
      work_id: '1907_EC',
      section_path: '',
      paragraph_ids: ['1907_EC_p5'],
      page_start: { number: null, display: '' },
      page_end: { number: null, display: '' },
      text: 'Le chunk retrouvé.',
      score: 0.8,
    }
    renderRailWithNeighbor(NEIGHBOR, [retrieved])

    const card = screen.getByTestId(`chunk-card-${NEIGHBOR.chunk_id}`)
    expect(within(card).queryByTestId('chunk-offset')).not.toBeInTheDocument()
  })

  it('counts a neighbor-origin inclusion toward the same shared x/5 counter', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })))
    renderRailWithNeighbor(NEIGHBOR)

    // chunkA defaults to included (only 1 retrieved chunk, DEFAULT_INCLUDED_COUNT=3
    // covers it) + the neighbor = 2.
    expect(screen.getByTestId('included-count')).toHaveTextContent('2/5 passages sélectionnés')
  })

  it('excluding a neighbor-origin card removes it entirely, not just greys it out', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })))
    const user = userEvent.setup()
    renderRailWithNeighbor(NEIGHBOR)

    const card = screen.getByTestId(`chunk-card-${NEIGHBOR.chunk_id}`)
    await user.click(within(card).getByText('Exclure'))

    expect(screen.queryByTestId(`chunk-card-${NEIGHBOR.chunk_id}`)).not.toBeInTheDocument()
    expect(screen.queryByTestId('neighbor-rail')).not.toBeInTheDocument()
    expect(screen.getByTestId('included-count')).toHaveTextContent('1/5 passages sélectionnés')
  })

  it('renders no second rail or title when no chunk was included via neighbor exploration', () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })))
    renderRailWithNeighbor(null)

    expect(screen.queryByTestId('neighbor-rail')).not.toBeInTheDocument()
    expect(screen.queryByText('Chunks voisins ajoutés manuellement')).not.toBeInTheDocument()
  })
})

// docs/ROADMAP.md, chunk-neighbor-persistence fix: a manually-included
// neighbor chunk was previously lost on reload (state/turnUi.tsx's
// `neighbors` map was client-only) — this debounced sync persists it via
// POST /turns/{id}/neighbor-chunks, the same fix that resolves a past
// generation showing "Œuvre inconnue" for it (lib/generationChunks.ts).
describe('ChunkRail — neighbor-chunks persistence sync', () => {
  it('persists the included neighbor chunk_ids once the debounce settles', async () => {
    vi.spyOn(api, 'setIncludedChunks').mockResolvedValue({ chunk_ids: [] })
    const setNeighborChunks = vi
      .spyOn(api, 'setNeighborChunks')
      .mockResolvedValue({ chunk_ids: [] })
    vi.spyOn(api, 'confidencePreview').mockResolvedValue({ retrieval_confidence_tier: 'moyenne' })

    renderRailWithNeighbor(NEIGHBOR)

    await waitFor(() =>
      expect(setNeighborChunks).toHaveBeenLastCalledWith(1, { chunk_ids: [NEIGHBOR.chunk_id] }),
    )
  })

  it('persists an empty neighbor list after excluding the last one', async () => {
    vi.spyOn(api, 'setIncludedChunks').mockResolvedValue({ chunk_ids: [] })
    const setNeighborChunks = vi
      .spyOn(api, 'setNeighborChunks')
      .mockResolvedValue({ chunk_ids: [] })
    vi.spyOn(api, 'confidencePreview').mockResolvedValue({ retrieval_confidence_tier: 'moyenne' })
    const user = userEvent.setup()

    renderRailWithNeighbor(NEIGHBOR)
    await waitFor(() =>
      expect(setNeighborChunks).toHaveBeenLastCalledWith(1, { chunk_ids: [NEIGHBOR.chunk_id] }),
    )

    const card = screen.getByTestId(`chunk-card-${NEIGHBOR.chunk_id}`)
    await user.click(within(card).getByText('Exclure'))

    await waitFor(() =>
      expect(setNeighborChunks).toHaveBeenLastCalledWith(1, { chunk_ids: [] }),
    )
  })
})
