import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Conversation } from './Conversation'
import { TurnUiProvider } from '../state/turnUi'

function chunk(id: string) {
  return {
    chunk_id: id,
    work_id: 'W',
    section_path: '',
    paragraph_ids: [],
    page_start: { number: null, display: '' },
    page_end: { number: null, display: '' },
    text: `Texte ${id}`,
    score: 0.5,
  }
}

const CHUNKS = ['c1', 'c2', 'c3', 'c4', 'c5'].map(chunk)

// Regression test for a bug where the freshly-created turn's <TurnCard>
// (holding client-only chunk include/exclude state, state/turnUi.tsx) got
// swapped for a second, separately-hydrated <TurnCard> instance as soon as
// the conversation's turns list caught up (see the comment above
// `draftTurnIds` in Conversation.tsx) — a chunk excluded right around that
// swap could land on the about-to-be-discarded instance and silently be
// lost, so Générer sent every chunk instead of only the included ones.
// Since turn/conversation creation now happens at /retrieve, not /generate
// (docs/ROADMAP.md, Sprint 10 turn-lifecycle fix), the redirect that
// triggers this swap fires right after retrieval — before any generation
// exists yet — so the exclusions below race that swap ahead of the turn's
// very first, manually-triggered "Générer" click.
describe('Conversation — draft turn stays on one controller instance', () => {
  let generateBodies: Array<{ chunks: { chunk_id: string }[] }> = []

  beforeEach(() => {
    generateBodies = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        const ok = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: async () => body })
        if (url.endsWith('/retrieve')) return ok({ turn_id: 1, conversation_id: 1, chunks: CHUNKS })
        if (url.endsWith('/generate')) {
          const body = JSON.parse(init!.body as string)
          generateBodies.push(body)
          return ok({
            answer: `Réponse ${generateBodies.length}`,
            model_used: 'test-model',
            generation_id: generateBodies.length,
            turn_id: 1,
            conversation_id: 1,
          })
        }
        if (url.endsWith('/evaluate')) {
          return ok({
            structural: { citations: [], unknown_citations: [], has_citation: true, fabricated_titles: [], passed: true },
            faithfulness: { score: 1, model: 'judge', claims: [] },
            should_auto_expand: false,
          })
        }
        if (url.endsWith('/confidence-preview')) {
          return ok({ retrieval_confidence_tier: 'moyenne' })
        }
        if (url.includes('/conversations/1') && !url.includes('/turns')) {
          return ok({ conversation_id: 1, turns: [{ turn_id: 1, query: 'Q', created_at: 'now' }] })
        }
        if (url.endsWith('/turns/1')) {
          return ok({
            turn_id: 1,
            conversation_id: 1,
            query: 'Q',
            created_at: 'now',
            retrieved_chunks: CHUNKS.map((c, i) => ({ ...c, rank: i })),
            generations: generateBodies.map((b, i) => ({
              generation_id: i + 1,
              model: 'test-model',
              chunk_ids: b.chunks.map((c) => c.chunk_id),
              answer: `Réponse ${i + 1}`,
              chunk_judgments_used: null,
              created_at: 'now',
              evaluation: null,
            })),
            chunk_judgments: {},
          })
        }
        throw new Error(`Unhandled fetch: ${url}`)
      }),
    )
  })

  it('keeps chunk exclusions made right after retrieval once the turns list catches up', async () => {
    const user = userEvent.setup()
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <TurnUiProvider>
          <MemoryRouter initialEntries={['/new']}>
            <Routes>
              <Route path="/new" element={<Conversation />} />
              <Route path="/new/:draftId" element={<Conversation />} />
              <Route path="/c/:conversationId" element={<Conversation />} />
            </Routes>
          </MemoryRouter>
        </TurnUiProvider>
      </QueryClientProvider>,
    )

    const input = await screen.findByPlaceholderText(/./)
    await user.type(input, 'Ma question{Enter}')

    await screen.findByText('Générer')
    // No settle wait: exclude immediately, the way an impatient real user
    // would, racing the conversation-list refetch this component triggers
    // right after retrieval creates the turn.
    const excludeButtons = await screen.findAllByText('Exclure')
    expect(excludeButtons).toHaveLength(5)
    for (const btn of excludeButtons.slice(1)) {
      await user.click(btn)
    }

    await user.click(screen.getByText('Générer'))
    await waitFor(() => expect(generateBodies).toHaveLength(1))
    expect(generateBodies[0].chunks.map((c) => c.chunk_id)).toEqual(['c1'])
  })
})

const NOTE_TEXT = 'Chaque question est traitée indépendamment, sans mémoire des échanges précédents.'

// Sprint 8 addendum: no cross-turn context — the transparency note must
// only appear once a prior turn already exists in the conversation, not on
// an empty one where it wouldn't yet be relevant.
describe('Conversation — no-cross-turn-context transparency note', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        const ok = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: async () => body })
        if (url.endsWith('/conversations/1')) {
          return ok({ conversation_id: 1, turns: [{ turn_id: 1, query: 'Q', created_at: 'now' }] })
        }
        if (url.endsWith('/turns/1')) {
          return ok({
            turn_id: 1,
            conversation_id: 1,
            query: 'Q',
            created_at: 'now',
            retrieved_chunks: [],
            generations: [],
            chunk_judgments: {},
          })
        }
        throw new Error(`Unhandled fetch: ${url}`)
      }),
    )
  })

  it('is absent on a brand-new, empty conversation', async () => {
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <TurnUiProvider>
          <MemoryRouter initialEntries={['/new']}>
            <Routes>
              <Route path="/new" element={<Conversation />} />
            </Routes>
          </MemoryRouter>
        </TurnUiProvider>
      </QueryClientProvider>,
    )

    await screen.findByPlaceholderText(/./)
    expect(screen.queryByText(NOTE_TEXT)).not.toBeInTheDocument()
  })

  it('appears near the input once a first turn already exists', async () => {
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <TurnUiProvider>
          <MemoryRouter initialEntries={['/c/1']}>
            <Routes>
              <Route path="/c/:conversationId" element={<Conversation />} />
            </Routes>
          </MemoryRouter>
        </TurnUiProvider>
      </QueryClientProvider>,
    )

    await waitFor(() => expect(screen.getByText(NOTE_TEXT)).toBeInTheDocument())
  })
})
