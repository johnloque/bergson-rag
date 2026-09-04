import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from '../App'
import { TurnUiProvider } from '../state/turnUi'

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}

// Regression test: a freshly submitted query used to be invisible in the
// sidebar's conversation list until the *entire* /retrieve response came
// back (hybrid search + reranking included), even though the conversation
// row is committed server-side well before that (src/api/main.py's
// /retrieve calls persistence.create_turn before running retrieval). Worse,
// the placeholder that was added for this couldn't be clicked back into —
// a user who navigated away while it was still running had no way back to
// it at all until it resolved on its own, and no sign it was even still
// running. `/new/:draftId` (App.tsx) plus state/pendingConversations.ts fix
// both: the sidebar row is a real link the whole time, and revisiting it
// reattaches to the one /retrieve call already in flight instead of firing
// a second one.
describe('Sidebar — pending new-conversation placeholder', () => {
  it('is clickable while pending, reattaches instead of re-calling /retrieve, and resolves into the real row', async () => {
    const user = userEvent.setup()
    let resolveRetrieve: (value: unknown) => void = () => {}
    const pendingRetrieve = new Promise((resolve) => {
      resolveRetrieve = resolve
    })
    let retrieveCallCount = 0
    let conversationsCallCount = 0

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.endsWith('/conversations')) {
          conversationsCallCount += 1
          if (conversationsCallCount === 1) return jsonResponse({ conversations: [] })
          return jsonResponse({
            conversations: [
              { conversation_id: 5, created_at: 'now', title: null, first_query: 'Ma question' },
            ],
          })
        }
        if (url.endsWith('/retrieve')) {
          retrieveCallCount += 1
          return pendingRetrieve.then(jsonResponse)
        }
        throw new Error(`Unhandled fetch: ${url}`)
      }),
    )

    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <TurnUiProvider>
          <MemoryRouter initialEntries={['/new']}>
            <AppRoutes />
          </MemoryRouter>
        </TurnUiProvider>
      </QueryClientProvider>,
    )

    const input = await screen.findByPlaceholderText(/./)
    await user.type(input, 'Ma question{Enter}')

    // Visible in the sidebar, and clickable, well before /retrieve resolves.
    const pendingRow = await screen.findByTitle(/Création de la conversation en cours/)
    expect(screen.queryByTestId('turn-card')).toBeInTheDocument()
    expect(retrieveCallCount).toBe(1)

    // Leave the page entirely (a different route, not just a re-render).
    await user.click(screen.getByText("Guide d'utilisation"))
    await waitFor(() => expect(screen.queryByTestId('turn-card')).not.toBeInTheDocument())

    // Come back via the sidebar's pending row instead of waiting.
    await user.click(pendingRow)
    await screen.findByTestId('turn-card')
    await screen.findByText('Recherche des passages pertinents')
    // Reattached to the same call -- did not fire a second /retrieve.
    expect(retrieveCallCount).toBe(1)

    resolveRetrieve({ turn_id: 1, conversation_id: 5, chunks: [] })

    // The pending placeholder is replaced by the real, persisted sidebar
    // row once /retrieve (and the resulting conversations refetch)
    // resolves, not left dangling alongside it.
    await waitFor(() => expect(conversationsCallCount).toBeGreaterThan(1))
    await screen.findByRole('button', { name: 'Ma question' })
    expect(screen.queryByTitle(/Création de la conversation en cours/)).not.toBeInTheDocument()
  })
})
