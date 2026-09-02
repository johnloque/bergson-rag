import { useEffect } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ChunkRail } from './ChunkRail'
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
  it('appends a neighbor-origin card after the retrieved candidates, with a dashed divider and the real citation', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })))
    renderRailWithNeighbor(NEIGHBOR)

    expect(screen.getByTestId('neighbor-divider')).toBeInTheDocument()
    const card = screen.getByTestId(`chunk-card-${NEIGHBOR.chunk_id}`)
    expect(card).toHaveAttribute('data-included', 'true')
    expect(card).toHaveAttribute('data-origin', 'neighbor')
    expect(within(card).getByTestId('chunk-citation')).toHaveTextContent(formatCitation(NEIGHBOR))
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
    expect(screen.queryByTestId('neighbor-divider')).not.toBeInTheDocument()
    expect(screen.getByTestId('included-count')).toHaveTextContent('1/5 passages sélectionnés')
  })

  it('renders no divider or neighbor cards when no chunk was included via neighbor exploration', () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })))
    renderRailWithNeighbor(null)

    expect(screen.queryByTestId('neighbor-divider')).not.toBeInTheDocument()
  })
})
