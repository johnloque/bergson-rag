import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ChunkRail } from './ChunkRail'
import { api } from '../api/client'
import { formatCitation } from '../lib/citation'
import { TurnUiProvider, useTurnUi } from '../state/turnUi'
import type { ChunkResult, ConfidencePreviewChunk, RetrievalConfidenceTier } from '../api/types'

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
const chunkB: ChunkResult = { ...chunkA, chunk_id: 'W_c2', text: 'Un autre passage.', score: 0.2 }

// docs/ROADMAP.md, Sprint 12: the rail shows the top 15 post-reranking
// chunks — same reranked order (rank 0 = highest, index 0) /retrieve
// returns, which drives which 3 default to included.
const FIFTEEN_CHUNKS: ChunkResult[] = Array.from({ length: 15 }, (_, i) => ({
  ...chunkA,
  chunk_id: `W_c${i + 1}`,
  score: 1 - i * 0.01,
}))

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}

afterEach(() => {
  vi.restoreAllMocks()
})

function renderRail(chunks: ChunkResult[] = [chunkA]) {
  return render(
    <TurnUiProvider>
      <MemoryRouter>
        <ChunkRail chunks={chunks} turnId={1} conversationId={1} />
      </MemoryRouter>
    </TurnUiProvider>,
  )
}

// state/useTurnController.ts calls turnUi.initTurn(turnId, chunkIds) right
// after a real /retrieve resolves — that's what actually seeds the
// top-DEFAULT_INCLUDED_COUNT-included default (state/turnUi.tsx), before
// ChunkRail ever reads inclusion state. The plain `renderRail` helper above
// never calls it, so `getIncluded`'s own `?? true` fallback is what makes a
// never-initialized chunk look included there — fine for tests only
// exercising toggle behavior on 1-2 chunks, but not a stand-in for the real
// default-selection logic under test below.
function renderInitializedRail(chunks: ChunkResult[], turnId = 1) {
  function Harness() {
    const turnUi = useTurnUi()
    useEffect(() => {
      turnUi.initTurn(
        turnId,
        chunks.map((c) => c.chunk_id),
      )
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
    return <ChunkRail chunks={chunks} turnId={turnId} conversationId={1} />
  }
  return render(
    <TurnUiProvider>
      <MemoryRouter>
        <Harness />
      </MemoryRouter>
    </TurnUiProvider>,
  )
}

describe('ChunkRail', () => {
  it('starts included by default and toggles to excluded on click', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })),
    )
    const user = userEvent.setup()
    renderRail()

    const card = screen.getByTestId('chunk-card-W_c1')
    expect(card).toHaveAttribute('data-included', 'true')
    expect(screen.getByText('Inclus')).toBeInTheDocument()

    await user.click(screen.getByText('Exclure'))

    expect(card).toHaveAttribute('data-included', 'false')
    expect(screen.getByText('Exclu')).toBeInTheDocument()
    expect(screen.getByText('Inclure')).toBeInTheDocument()
  })

  it('shows the shared citation format (work, year, paragraph) instead of the bare work_id', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })),
    )
    const citedChunk: ChunkResult = {
      ...chunkA,
      chunk_id: '1907_EC_c5',
      work_id: '1907_EC',
      paragraph_ids: ['1907_EC_p5'],
    }
    renderRail([citedChunk])

    const card = screen.getByTestId('chunk-card-1907_EC_c5')
    const citation = within(card).getByTestId('chunk-citation')
    expect(citation).toHaveTextContent(formatCitation(citedChunk))
    expect(citation).toHaveTextContent("L'Évolution créatrice (1907), paragraphe 5")
    // The old display was just the bare work_id ("1907_EC") — the real
    // citation replaces it, not sits alongside it.
    expect(within(card).queryByText('1907_EC')).not.toBeInTheDocument()
  })
})

describe('ChunkRail — default selection and the 5-chunk cap (docs/ROADMAP.md, Sprint 12)', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ retrieval_confidence_tier: 'moyenne' })),
    )
  })

  it('checks exactly the top 3 of 15 chunks by default, in reranked order', () => {
    renderInitializedRail(FIFTEEN_CHUNKS)

    const includedIds = FIFTEEN_CHUNKS.filter(
      (c) => screen.getByTestId(`chunk-card-${c.chunk_id}`).getAttribute('data-included') === 'true',
    ).map((c) => c.chunk_id)
    expect(includedIds).toEqual(['W_c1', 'W_c2', 'W_c3'])
    expect(screen.getByTestId('included-count')).toHaveTextContent('3/5 passages sélectionnés')
  })

  it('allows selecting up to 5 chunks total', async () => {
    const user = userEvent.setup()
    renderInitializedRail(FIFTEEN_CHUNKS)

    await user.click(within(screen.getByTestId('chunk-card-W_c4')).getByText('Inclure'))
    await user.click(within(screen.getByTestId('chunk-card-W_c5')).getByText('Inclure'))

    expect(screen.getByTestId('chunk-card-W_c4')).toHaveAttribute('data-included', 'true')
    expect(screen.getByTestId('chunk-card-W_c5')).toHaveAttribute('data-included', 'true')
    expect(screen.getByTestId('included-count')).toHaveTextContent('5/5 passages sélectionnés (maximum atteint)')
  })

  it('blocks a 6th selection: the "Inclure" button on every other excluded chunk is disabled, and the click is a no-op', async () => {
    const user = userEvent.setup()
    renderInitializedRail(FIFTEEN_CHUNKS)

    await user.click(within(screen.getByTestId('chunk-card-W_c4')).getByText('Inclure'))
    await user.click(within(screen.getByTestId('chunk-card-W_c5')).getByText('Inclure'))

    const sixthButton = within(screen.getByTestId('chunk-card-W_c6')).getByText('Inclure')
    expect(sixthButton).toBeDisabled()

    await user.click(sixthButton)

    expect(screen.getByTestId('chunk-card-W_c6')).toHaveAttribute('data-included', 'false')
    expect(screen.getByTestId('included-count')).toHaveTextContent('5/5 passages sélectionnés (maximum atteint)')
  })

  it('excluding an included chunk frees up a slot for another one', async () => {
    const user = userEvent.setup()
    renderInitializedRail(FIFTEEN_CHUNKS)

    await user.click(within(screen.getByTestId('chunk-card-W_c4')).getByText('Inclure'))
    await user.click(within(screen.getByTestId('chunk-card-W_c5')).getByText('Inclure'))
    await user.click(within(screen.getByTestId('chunk-card-W_c1')).getByText('Exclure'))

    expect(screen.getByTestId('chunk-card-W_c1')).toHaveAttribute('data-included', 'false')
    const sixthButton = within(screen.getByTestId('chunk-card-W_c6')).getByText('Inclure')
    expect(sixthButton).not.toBeDisabled()

    await user.click(sixthButton)
    expect(screen.getByTestId('chunk-card-W_c6')).toHaveAttribute('data-included', 'true')
  })
})

describe('ChunkRail confidence gauge', () => {
  let requestedChunks: ConfidencePreviewChunk[][]

  beforeEach(() => {
    requestedChunks = []
  })

  // Spying on api.confidencePreview directly (not the global fetch) keeps
  // assertions focused on what ChunkRail sends and how often — the real
  // endpoint is exercised by the backend's own tests (tests/test_api.py).
  function stubConfidencePreview(tierByRequestIndex: RetrievalConfidenceTier[]) {
    vi.spyOn(api, 'confidencePreview').mockImplementation(async (body) => {
      requestedChunks.push(body.chunks)
      const tier = tierByRequestIndex[requestedChunks.length - 1] ?? tierByRequestIndex.at(-1)!
      return { retrieval_confidence_tier: tier }
    })
  }

  it('renders near the chunk rail once /confidence-preview resolves', async () => {
    stubConfidencePreview(['moyenne'])
    renderRail([chunkA])

    expect(screen.queryByText('Confiance du retrieval')).not.toBeInTheDocument()

    await waitFor(() => expect(screen.getByText('Confiance du retrieval')).toBeInTheDocument())
    expect(screen.getByRole('img', { name: 'Confiance : moyenne' })).toBeInTheDocument()
    expect(requestedChunks[0]).toEqual([{ chunk_id: 'W_c1', score: 0.5 }])
  })

  it('debounces rapid toggles into a single trailing request reflecting the final included set', async () => {
    stubConfidencePreview(['moyenne', 'très faible'])
    const user = userEvent.setup()
    renderRail([chunkA, chunkB])

    await waitFor(() => expect(requestedChunks).toHaveLength(1))
    expect(requestedChunks[0]).toEqual([
      { chunk_id: 'W_c1', score: 0.5 },
      { chunk_id: 'W_c2', score: 0.2 },
    ])

    // Three rapid toggles inside the ~300ms debounce window (exclude B,
    // re-include B, exclude B again) must coalesce into a single trailing
    // request reflecting only the final included set — not one request per
    // click (docs/ROADMAP.md, the retrieval-confidence-split correction).
    await user.click(screen.getAllByText('Exclure')[1])
    await user.click(screen.getAllByText('Inclure')[0])
    await user.click(screen.getAllByText('Exclure')[1])

    await waitFor(() => expect(requestedChunks).toHaveLength(2))
    expect(requestedChunks[1]).toEqual([{ chunk_id: 'W_c1', score: 0.5 }])
    await waitFor(() =>
      expect(screen.getByRole('img', { name: 'Confiance : très faible' })).toBeInTheDocument(),
    )
  })
})

// docs/ROADMAP.md, chunk-neighbor-persistence fix: the rail's included set
// was previously client-only (state/turnUi.tsx) and lost on reload — this
// debounced effect (same trigger/timing as the confidence-preview one
// above) persists it via POST /turns/{id}/included-chunks so GET
// /turns/{id} can restore it later.
describe('ChunkRail — included-chunks persistence sync', () => {
  function stubPersistence() {
    const setIncludedChunks = vi
      .spyOn(api, 'setIncludedChunks')
      .mockResolvedValue({ chunk_ids: [] })
    vi.spyOn(api, 'setNeighborChunks').mockResolvedValue({ chunk_ids: [] })
    vi.spyOn(api, 'confidencePreview').mockResolvedValue({ retrieval_confidence_tier: 'moyenne' })
    return setIncludedChunks
  }

  it('persists the default-included chunk_ids once the debounce settles', async () => {
    const setIncludedChunks = stubPersistence()
    renderInitializedRail([chunkA, chunkB])

    await waitFor(() =>
      expect(setIncludedChunks).toHaveBeenCalledWith(1, { chunk_ids: ['W_c1', 'W_c2'] }),
    )
  })

  it('persists the narrowed set after excluding a chunk', async () => {
    const setIncludedChunks = stubPersistence()
    const user = userEvent.setup()
    renderInitializedRail([chunkA, chunkB])
    await waitFor(() => expect(setIncludedChunks).toHaveBeenCalledTimes(1))

    await user.click(screen.getAllByText('Exclure')[1])

    await waitFor(() =>
      expect(setIncludedChunks).toHaveBeenLastCalledWith(1, { chunk_ids: ['W_c1'] }),
    )
  })
})
