import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
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
          return jsonResponse({ turn_id: 1, conversation_id: 1, chunks: [CHUNK_A, CHUNK_B] })
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
              should_auto_expand: false,
            }),
          )
        }
        if (url.endsWith('/confidence-preview')) {
          return jsonResponse({ retrieval_confidence_tier: 'moyenne' })
        }
        throw new Error(`Unhandled fetch: ${url}`)
      }),
    )
  })

  it('does not auto-generate after retrieval — shows a "Générer" trigger instead', async () => {
    renderTurnCard()
    await screen.findByTestId('chunk-rail')

    expect(screen.getByText('Générer')).toBeInTheDocument()
    expect(
      (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url]) =>
        url.endsWith('/generate'),
      ),
    ).toBe(false)
  })

  it('reveals immediately via "Lire quand même" and applies annotations once /evaluate resolves later', async () => {
    const user = userEvent.setup()
    renderTurnCard()

    await user.click(await screen.findByText('Générer'))
    const revealButton = await screen.findByText('Lire quand même')
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'blur(5px)' })

    await user.click(revealButton)
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'none' })
    expect(screen.queryByText('Lire quand même')).not.toBeInTheDocument()
    expect(
      within(screen.getByTestId('answer-card')).queryByText('Confiance du retrieval'),
    ).not.toBeInTheDocument()

    // /evaluate is never auto-triggered — it only runs once "Évaluer" is clicked.
    await user.click(screen.getByText('Évaluer'))
    resolveEvaluate()
    await waitFor(() => expect(screen.getByText('Vérification terminée')).toBeInTheDocument())
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'none' })
    // The confidence gauge never appears in the answer card, evaluated or
    // not (docs/ROADMAP.md, the retrieval-confidence-split correction) —
    // it's shown pre-generation, at the chunk-rail level, instead.
    expect(
      within(screen.getByTestId('answer-card')).queryByText('Confiance du retrieval'),
    ).not.toBeInTheDocument()
  })

  it('never calls /evaluate until "Évaluer" is clicked', async () => {
    const user = userEvent.setup()
    renderTurnCard()
    await user.click(await screen.findByText('Générer'))
    await screen.findByText('Lire quand même')

    expect(screen.getByText('Non vérifié')).toBeInTheDocument()
    expect(
      (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(([url]) =>
        url.endsWith('/evaluate'),
      ),
    ).toBe(false)
  })

  it('shows Générer before the first generation, then Régénérer once it completes', async () => {
    const user = userEvent.setup()
    renderTurnCard()
    await screen.findByText('Générer')
    expect(screen.queryByText('Régénérer')).not.toBeInTheDocument()

    await user.click(screen.getByText('Générer'))
    await screen.findByText('Lire quand même')
    expect(screen.getByText('Régénérer')).toBeInTheDocument()
    expect(screen.queryByText('Générer')).not.toBeInTheDocument()
  })

  it('reflects a chunk rail exclusion in the next /generate call', async () => {
    const user = userEvent.setup()
    renderTurnCard()

    await user.click(await screen.findByText('Générer'))
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

// Regression test for the "vérifié status lost on navigation" bug
// (docs/ROADMAP.md, Sprint 10): a full retrieve -> manual generate ->
// evaluate cycle, then a simulated "navigate away and back" (the component
// unmounts and a fresh one mounts with the same turnId, exactly like
// react-router remounting <TurnCard> from a persisted conversation's turns
// list) — GET /turns/{id} must drive the same non-blurred, correctly-badged
// display as the live session did, not reset to the pre-evaluation
// collapsed/blurred state.
describe('TurnCard full cycle survives a simulated navigate-away-and-back', () => {
  it('stays expanded (should_auto_expand true) after a fresh mount hydrates from GET /turns/{id}', async () => {
    const user = userEvent.setup()

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.endsWith('/retrieve')) {
          return jsonResponse({ turn_id: 1, conversation_id: 1, chunks: [CHUNK_A] })
        }
        if (url.endsWith('/generate')) {
          return jsonResponse({
            answer: 'Réponse fondée [W_c1].',
            model_used: 'test-model',
            generation_id: 7,
            turn_id: 1,
            conversation_id: 1,
          })
        }
        if (url.endsWith('/evaluate')) {
          return jsonResponse({
            structural: { citations: ['W_c1'], unknown_citations: [], has_citation: true, passed: true },
            faithfulness: { score: 1, model: 'judge', claims: [] },
            should_auto_expand: true,
          })
        }
        if (url.endsWith('/confidence-preview')) {
          return jsonResponse({ retrieval_confidence_tier: 'élevée' })
        }
        if (url.endsWith('/turns/1')) {
          return jsonResponse({
            turn_id: 1,
            conversation_id: 1,
            query: 'Quelle est la nature du temps ?',
            created_at: new Date().toISOString(),
            retrieved_chunks: [{ ...CHUNK_A, rank: 0 }],
            chunk_judgments: {},
            generations: [
              {
                generation_id: 7,
                model: 'test-model',
                chunk_ids: [CHUNK_A.chunk_id],
                answer: 'Réponse fondée [W_c1].',
                chunk_judgments_used: null,
                created_at: new Date().toISOString(),
                evaluation: {
                  structural: {
                    citations: ['W_c1'],
                    unknown_citations: [],
                    has_citation: true,
                    passed: true,
                  },
                  faithfulness: { score: 1, model: 'judge', claims: [] },
                  should_auto_expand: true,
                },
              },
            ],
          })
        }
        throw new Error(`Unhandled fetch: ${url}`)
      }),
    )

    const client = new QueryClient()
    const first = render(
      <QueryClientProvider client={client}>
        <TurnUiProvider>
          <MemoryRouter>
            <TurnCard pendingQuery="Quelle est la nature du temps ?" />
          </MemoryRouter>
        </TurnUiProvider>
      </QueryClientProvider>,
    )

    await user.click(await screen.findByText('Générer'))
    await screen.findByText('Évaluer')
    await user.click(screen.getByText('Évaluer'))
    await waitFor(() => expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'none' }))

    // Navigate away: the live TurnCard/useTurnController instance is gone.
    first.unmount()

    // Navigate back: a brand-new instance, hydrating purely from
    // GET /turns/{id} — no client-only "revealed" state survives, and none
    // should be needed since should_auto_expand alone must drive this.
    render(
      <QueryClientProvider client={client}>
        <TurnUiProvider>
          <MemoryRouter>
            <TurnCard turnId={1} conversationId={1} />
          </MemoryRouter>
        </TurnUiProvider>
      </QueryClientProvider>,
    )

    const content = await screen.findByTestId('answer-content')
    expect(content).toHaveStyle({ filter: 'none' })
    expect(screen.queryByText('Lire quand même')).not.toBeInTheDocument()
  })
})
