import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
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

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}

interface HydratedFilter {
  work_ids: string[] | null
  date_range: { start: number; end: number; mode: string } | null
}

// The real backend always includes work_ids/date_range on GET /turns/{id}
// (src/api/schemas.py's TurnDetailResponse, Sprint 12 filter UI) — null
// for both means "no filter was applied", never an absent key. `hydrated`
// lets a test stand in for either case.
function stubRetrieveAndTurn(hydrated: HydratedFilter = { work_ids: null, date_range: null }) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.endsWith('/retrieve')) return jsonResponse({ turn_id: 1, conversation_id: 1, chunks: [CHUNK_A] })
      if (url.endsWith('/confidence-preview')) return jsonResponse({ retrieval_confidence_tier: 'moyenne' })
      if (url.endsWith('/turns/1')) {
        return jsonResponse({
          turn_id: 1,
          conversation_id: 1,
          query: 'Q',
          created_at: 'now',
          retrieved_chunks: [{ ...CHUNK_A, rank: 0 }],
          generations: [],
          chunk_judgments: {},
          ...hydrated,
        })
      }
      throw new Error(`Unhandled fetch: ${url}`)
    }),
  )
}

function renderWithClient(node: React.ReactElement) {
  const client = new QueryClient()
  return render(
    <QueryClientProvider client={client}>
      <TurnUiProvider>
        <MemoryRouter>{node}</MemoryRouter>
      </TurnUiProvider>
    </QueryClientProvider>,
  )
}

describe('TurnCard — expandable "sources considered" detail', () => {
  it('shows a chevron once retrieval is done, and reveals the full 8-work list on click when no filter was applied', async () => {
    stubRetrieveAndTurn()
    const user = userEvent.setup()
    renderWithClient(<TurnCard pendingQuery="Une question" conversationId={1} filterParams={{}} />)

    const toggle = await screen.findByRole('button', { name: 'Afficher les sources prises en compte' })
    expect(screen.queryByTestId('considered-sources')).not.toBeInTheDocument()

    await user.click(toggle)

    const list = screen.getByTestId('considered-sources')
    expect(list).toHaveTextContent('Essai sur les données immédiates de la conscience (1888)')
    expect(list).toHaveTextContent('La Pensée et le Mouvant (1934)')

    await user.click(screen.getByRole('button', { name: 'Masquer les sources prises en compte' }))
    expect(screen.queryByTestId('considered-sources')).not.toBeInTheDocument()
  })

  it('lists only the restricted works when work_ids narrows the filter', async () => {
    stubRetrieveAndTurn()
    const user = userEvent.setup()
    renderWithClient(
      <TurnCard
        pendingQuery="Une question ciblée"
        conversationId={1}
        filterParams={{ work_ids: ['1888_EDIC', '1896_MM'] }}
      />,
    )

    await user.click(await screen.findByRole('button', { name: 'Afficher les sources prises en compte' }))
    const list = screen.getByTestId('considered-sources')
    expect(list).toHaveTextContent('Essai sur les données immédiates de la conscience (1888)')
    expect(list).toHaveTextContent('Matière et mémoire (1896)')
    expect(list).not.toHaveTextContent('La Pensée et le Mouvant')
  })

  it('nests the qualifying individual texts under an anthology work in "text" mode', async () => {
    stubRetrieveAndTurn()
    const user = userEvent.setup()
    renderWithClient(
      <TurnCard
        pendingQuery="Une question datée"
        conversationId={1}
        filterParams={{
          work_ids: ['1919_ES'],
          date_range: { start: 1902, end: 1902, mode: 'text' },
        }}
      />,
    )

    await user.click(await screen.findByRole('button', { name: 'Afficher les sources prises en compte' }))
    const list = screen.getByTestId('considered-sources')
    expect(list).toHaveTextContent("L'énergie spirituelle (1919)")
    expect(list).toHaveTextContent("L'effort intellectuel (1902)")
  })

  it('shows the full 8-work list for a reloaded/hydrated turn that had no filter applied', async () => {
    stubRetrieveAndTurn({ work_ids: null, date_range: null })
    const user = userEvent.setup()
    renderWithClient(<TurnCard turnId={1} conversationId={1} />)

    await user.click(await screen.findByRole('button', { name: 'Afficher les sources prises en compte' }))
    const list = screen.getByTestId('considered-sources')
    expect(list).toHaveTextContent('Essai sur les données immédiates de la conscience (1888)')
    expect(list).toHaveTextContent('La Pensée et le Mouvant (1934)')
  })

  it('shows the narrowed list for a reloaded/hydrated turn that had a filter applied — survives the reload', async () => {
    stubRetrieveAndTurn({ work_ids: ['1888_EDIC', '1896_MM'], date_range: null })
    const user = userEvent.setup()
    renderWithClient(<TurnCard turnId={1} conversationId={1} />)

    await user.click(await screen.findByRole('button', { name: 'Afficher les sources prises en compte' }))
    const list = screen.getByTestId('considered-sources')
    expect(list).toHaveTextContent('Essai sur les données immédiates de la conscience (1888)')
    expect(list).toHaveTextContent('Matière et mémoire (1896)')
    expect(list).not.toHaveTextContent('La Pensée et le Mouvant')
  })
})
