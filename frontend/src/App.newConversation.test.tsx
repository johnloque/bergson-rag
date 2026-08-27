import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from './App'
import { TurnUiProvider } from './state/turnUi'

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}

// Regression test for the "nouvelle conversation" inactive-button bug
// (docs/ROADMAP.md, Sprint 10): react-router does not remount a route's
// element just because navigate() was called to the path it's already
// showing, so a second "Nouvelle conversation" click while already on /new
// used to be a no-op — Conversation's own `drafts`/`pendingCount` state
// (routes/Conversation.tsx) survived untouched instead of starting a
// genuinely fresh turn. Fixed by keying /new's <Conversation> on
// `location.key` (App.tsx), which changes on every navigation regardless of
// path.
describe('"Nouvelle conversation" while already on /new', () => {
  it('remounts Conversation and discards an in-flight draft instead of being a router no-op', async () => {
    const user = userEvent.setup()
    let resolveRetrieve: (value: unknown) => void = () => {}
    const pendingRetrieve = new Promise((resolve) => {
      resolveRetrieve = resolve
    })

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.endsWith('/conversations')) return jsonResponse({ conversations: [] })
        if (url.endsWith('/retrieve')) return pendingRetrieve.then(jsonResponse)
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

    // The draft is live: /retrieve is in flight and never resolved yet.
    await screen.findByText('Recherche des passages pertinents')

    // Still nominally on /new — click "Nouvelle conversation" again, the
    // exact reported scenario.
    await user.click(screen.getByText('Nouvelle conversation'))

    // A genuinely fresh turn: the stale in-flight draft's processing step
    // is gone, and the composer is usable again immediately (not stuck
    // "disabled" behind a pending count the remount never cleared).
    await waitFor(() =>
      expect(screen.queryByText('Recherche des passages pertinents')).not.toBeInTheDocument(),
    )
    const freshInput = await screen.findByPlaceholderText(/./)
    expect(freshInput).not.toBeDisabled()

    // The stale /retrieve call eventually resolves — since the component
    // that started it was discarded by the remount, this must not
    // resurrect a leftover draft/turn card.
    resolveRetrieve({ turn_id: 1, conversation_id: 1, chunks: [] })
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByTestId('turn-card')).not.toBeInTheDocument()
  })
})
