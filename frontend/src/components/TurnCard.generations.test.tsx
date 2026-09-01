import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { TurnCard } from './TurnCard'
import { TurnUiProvider } from '../state/turnUi'

const CHUNK_A = {
  chunk_id: '1907_EC_c1',
  work_id: '1907_EC',
  section_path: '',
  paragraph_ids: ['1907_EC_p5'],
  page_start: { number: null, display: '' },
  page_end: { number: null, display: '' },
  text: 'Texte du chunk A',
  score: 0.5,
}
const CHUNK_B = {
  ...CHUNK_A,
  chunk_id: '1907_EC_c2',
  paragraph_ids: ['1907_EC_p9'],
  text: 'Texte du chunk B',
}

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
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

function stubFetch(answers: string[]) {
  let generateCallCount = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.endsWith('/retrieve')) {
        return jsonResponse({ turn_id: 1, conversation_id: 1, chunks: [CHUNK_A, CHUNK_B] })
      }
      if (url.endsWith('/generate')) {
        const answer = answers[generateCallCount]
        generateCallCount += 1
        return jsonResponse({
          answer,
          model_used: 'test-model',
          generation_id: generateCallCount,
          turn_id: 1,
          conversation_id: 1,
        })
      }
      if (url.endsWith('/confidence-preview')) {
        return jsonResponse({ retrieval_confidence_tier: 'moyenne' })
      }
      throw new Error(`Unhandled fetch: ${url}`)
    }),
  )
}

describe('GenerationBlock — included chunks disclosure', () => {
  it('reuses the chevron disclosure to show/hide the included chunks, using the shared citation format', async () => {
    const user = userEvent.setup()
    stubFetch(['Réponse fondée [1907_EC_c1].'])
    renderTurnCard()

    await user.click(await screen.findByText('Générer'))
    await screen.findByText('Génération de la réponse')

    // Collapsed by default, same as the retrieval step's own expandable
    // detail (components/StepLine.tsx) — nothing shown until the chevron is
    // clicked.
    expect(screen.queryByTestId('included-chunks')).not.toBeInTheDocument()

    const toggle = screen.getByRole('button', { name: 'Afficher les passages inclus dans la génération' })
    await user.click(toggle)

    // The real citation format (docs/ROADMAP.md, Sprint 12,
    // lib/citation.ts) — no `[chunk_id]` fallback left, both default-
    // included chunks resolve to a distinct paragraph in the same work.
    const list = await screen.findByTestId('included-chunks')
    expect(within(list).getByText("L'Évolution créatrice (1907), paragraphe 5")).toBeInTheDocument()
    expect(within(list).getByText("L'Évolution créatrice (1907), paragraphe 9")).toBeInTheDocument()
    expect(within(list).queryByText(/\[1907_EC_c1\]/)).not.toBeInTheDocument()
    expect(within(list).queryByText(/\[1907_EC_c2\]/)).not.toBeInTheDocument()

    await user.click(toggle)
    expect(screen.queryByTestId('included-chunks')).not.toBeInTheDocument()
  })
})

describe('TurnCard — multiple generations on one turn', () => {
  it('shows the most recent generation primary and keeps older ones reachable, not deleted', async () => {
    const user = userEvent.setup()
    stubFetch(['Réponse A [1907_EC_c1].', 'Réponse B [1907_EC_c1].'])
    renderTurnCard()

    await user.click(await screen.findByText('Générer'))
    await screen.findByText('Régénérer')
    expect(screen.getByTestId('answer-content')).toHaveTextContent('Réponse A')

    await user.click(screen.getByText('Régénérer'))
    await waitFor(() => expect(screen.getAllByTestId('answer-card')).toHaveLength(1))

    // Most recent renders primary — no need to expand anything to see it.
    expect(screen.getByTestId('answer-content')).toHaveTextContent('Réponse B')
    expect(screen.queryByText('Réponse A', { exact: false })).not.toBeInTheDocument()

    // Older generation is reachable, not discarded (Sprint 7b: a generation
    // is never deleted once made) — behind the same collapsed-by-default
    // disclosure convention as everywhere else in this UI.
    const versionsToggle = screen.getByTestId('generation-versions-toggle')
    expect(versionsToggle).toHaveTextContent('1 version précédente')
    expect(screen.queryByTestId('generation-versions')).not.toBeInTheDocument()

    await user.click(versionsToggle)
    const older = await screen.findByTestId('generation-versions')
    expect(within(older).getByTestId('answer-content')).toHaveTextContent('Réponse A')

    // Both answer cards are present at once now: the primary (most recent)
    // and the disclosed older one.
    expect(screen.getAllByTestId('answer-card')).toHaveLength(2)
  })
})
