import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ChunkRail } from './ChunkRail'
import { api } from '../api/client'
import { TurnUiProvider } from '../state/turnUi'
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
