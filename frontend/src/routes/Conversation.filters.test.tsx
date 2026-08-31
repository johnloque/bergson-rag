import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Conversation } from './Conversation'
import { TurnUiProvider } from '../state/turnUi'

// Confirms the filter UI's request construction contract end-to-end
// (docs/ROADMAP.md, Sprint 12 filter UI): the default state omits both
// work_ids and date_range entirely rather than sending an explicit "all 8
// works, full span" default, an unchecked work narrows work_ids, and a
// moved slider sends date_range with whichever mode is currently selected.
// The backend's own filtering logic (feat/retrieval-filtering) is not
// re-tested here — only that this branch builds the right request body.

function renderConversation() {
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
}

function stubFetch(retrieveBodies: Record<string, unknown>[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const ok = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: async () => body })
      if (url.endsWith('/retrieve')) {
        const body = JSON.parse(init!.body as string)
        retrieveBodies.push(body)
        return ok({ turn_id: retrieveBodies.length, conversation_id: 1, chunks: [] })
      }
      if (url.includes('/conversations/1')) {
        return ok({ conversation_id: 1, turns: [] })
      }
      throw new Error(`Unhandled fetch: ${url}`)
    }),
  )
}

async function submit(user: ReturnType<typeof userEvent.setup>, query: string) {
  const input = await screen.findByPlaceholderText(/./)
  await user.type(input, `${query}{Enter}`)
}

async function openFilterPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: 'Filtrer les sources' }))
}

describe('Conversation — filter UI wires into /retrieve', () => {
  it('sends neither work_ids nor date_range when nothing was touched', async () => {
    const retrieveBodies: Record<string, unknown>[] = []
    stubFetch(retrieveBodies)
    const user = userEvent.setup()
    renderConversation()

    await submit(user, 'Une question')

    await waitFor(() => expect(retrieveBodies).toHaveLength(1))
    expect(retrieveBodies[0]).not.toHaveProperty('work_ids')
    expect(retrieveBodies[0]).not.toHaveProperty('date_range')
    expect(retrieveBodies[0].query).toBe('Une question')
  })

  it('sends the reduced work_ids list once a work is unchecked', async () => {
    const retrieveBodies: Record<string, unknown>[] = []
    stubFetch(retrieveBodies)
    const user = userEvent.setup()
    renderConversation()

    await openFilterPanel(user)
    await user.click(screen.getByLabelText(/Le rire/))
    await user.click(screen.getByLabelText(/Matière et mémoire/))

    await submit(user, 'Une question ciblée')

    await waitFor(() => expect(retrieveBodies).toHaveLength(1))
    const body = retrieveBodies[0] as { work_ids?: string[]; date_range?: unknown }
    expect(body.work_ids).not.toContain('1900_R')
    expect(body.work_ids).not.toContain('1896_MM')
    expect(body.work_ids).toHaveLength(6)
    expect(body.date_range).toBeUndefined()
  })

  it('sends date_range with the selected mode once the slider is moved', async () => {
    const retrieveBodies: Record<string, unknown>[] = []
    stubFetch(retrieveBodies)
    const user = userEvent.setup()
    renderConversation()

    await openFilterPanel(user)
    fireEvent.change(screen.getByLabelText('Année de début'), { target: { value: '1900' } })
    fireEvent.change(screen.getByLabelText('Année de fin'), { target: { value: '1920' } })
    await user.click(screen.getByRole('button', { name: 'Texte' }))

    await submit(user, 'Une question datée')

    await waitFor(() => expect(retrieveBodies).toHaveLength(1))
    const body = retrieveBodies[0] as { work_ids?: string[]; date_range?: { start: number; end: number; mode: string } }
    expect(body.date_range).toEqual({ start: 1900, end: 1920, mode: 'text' })
    expect(body.work_ids).toBeUndefined()
  })
})

describe('Conversation — filter control visual indicator', () => {
  it('shows the active-filter dot once a filter is set, and none by default', async () => {
    stubFetch([])
    const user = userEvent.setup()
    renderConversation()

    await screen.findByPlaceholderText(/./)
    expect(screen.queryByTestId('filter-active-indicator')).not.toBeInTheDocument()

    await openFilterPanel(user)
    await user.click(screen.getByLabelText(/Le rire/))

    expect(screen.getByTestId('filter-active-indicator')).toBeInTheDocument()
  })
})
