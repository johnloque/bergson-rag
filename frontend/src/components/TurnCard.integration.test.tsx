import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { TurnCard } from './TurnCard'
import { TurnUiProvider } from '../state/turnUi'

const CHUNK_A = {
  chunk_id: 'W_c1',
  work_id: 'W',
  section_path: '',
  paragraph_ids: [],
  page_start: { number: null, display: '' },
  page_end: { number: null, display: '' },
  text: 'Texte du chunk A',
  score: 0.5,
}
const CHUNK_B = { ...CHUNK_A, chunk_id: 'W_c2', text: 'Texte du chunk B' }

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve({ ok: true, status, json: async () => body })
}

function renderTurnCard() {
  const client = new QueryClient()
  return render(
    <QueryClientProvider client={client}>
      <TurnUiProvider>
        <MemoryRouter>
          <TurnCard pendingQuery="Quelle est la nature du temps ?" />
        </MemoryRouter>
      </TurnUiProvider>
    </QueryClientProvider>,
  )
}

describe('TurnCard integration', () => {
  let resolveEvaluate: () => void
  let generateBodies: Array<{ chunks: { chunk_id: string }[] }>

  beforeEach(() => {
    generateBodies = []
    const evaluatePromise = new Promise<void>((resolve) => {
      resolveEvaluate = resolve
    })

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith('/retrieve')) {
          return jsonResponse({ chunks: [CHUNK_A, CHUNK_B] })
        }
        if (url.endsWith('/generate')) {
          const body = JSON.parse(init!.body as string)
          generateBodies.push(body)
          return jsonResponse({
            answer: 'Réponse fondée [W_c1].',
            model_used: 'test-model',
            generation_id: generateBodies.length,
            turn_id: 1,
            conversation_id: 1,
          })
        }
        if (url.endsWith('/evaluate')) {
          return evaluatePromise.then(() =>
            jsonResponse({
              structural: { citations: ['W_c1'], unknown_citations: [], has_citation: true, passed: true },
              faithfulness: { score: 1, model: 'judge', claims: [] },
              retrieval_confidence_tier: 'moyenne',
              should_auto_expand: false,
            }),
          )
        }
        throw new Error(`Unhandled fetch: ${url}`)
      }),
    )
  })

  it('reveals immediately via "Lire quand même" and applies annotations once /evaluate resolves later', async () => {
    const user = userEvent.setup()
    renderTurnCard()

    const revealButton = await screen.findByText('Lire quand même')
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'blur(5px)' })

    await user.click(revealButton)
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'none' })
    expect(screen.queryByText('Lire quand même')).not.toBeInTheDocument()
    expect(screen.queryByText('Confiance du retrieval')).not.toBeInTheDocument()

    // /evaluate is never auto-triggered — it only runs once "Évaluer" is clicked.
    await user.click(screen.getByText('Évaluer'))
    resolveEvaluate()
    await waitFor(() => expect(screen.getByText('Confiance du retrieval')).toBeInTheDocument())
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'none' })
  })

  it('never calls /evaluate until "Évaluer" is clicked', async () => {
    renderTurnCard()
    await screen.findByText('Lire quand même')

    expect(screen.getByText('Non vérifié')).toBeInTheDocument()
    expect(
      (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url]: [string]) =>
        url.endsWith('/evaluate'),
      ),
    ).toBe(false)
  })

  it('shows Régénérer only after the first generation has completed', async () => {
    renderTurnCard()
    expect(screen.queryByText('Régénérer')).not.toBeInTheDocument()

    await screen.findByText('Lire quand même')
    expect(screen.getByText('Régénérer')).toBeInTheDocument()
  })

  it('reflects a chunk rail exclusion in the next /generate call', async () => {
    const user = userEvent.setup()
    renderTurnCard()

    await screen.findByText('Régénérer')
    expect(generateBodies).toHaveLength(1)
    expect(generateBodies[0].chunks.map((c) => c.chunk_id)).toEqual(['W_c1', 'W_c2'])

    const excludeButtons = screen.getAllByText('Exclure')
    await user.click(excludeButtons[1])

    resolveEvaluate()
    await user.click(screen.getByText('Régénérer'))

    await waitFor(() => expect(generateBodies).toHaveLength(2))
    expect(generateBodies[1].chunks.map((c) => c.chunk_id)).toEqual(['W_c1'])
  })
})
