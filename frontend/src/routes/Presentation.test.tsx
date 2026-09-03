import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Presentation } from './Presentation'

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}

describe('Presentation', () => {
  it('"Entrer dans l\'application" navigates to the last conversation when one exists', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({
          conversations: [{ conversation_id: 7, created_at: 'now', title: null, first_query: 'Q' }],
        }),
      ),
    )
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/presentation']}>
        <Routes>
          <Route path="/presentation" element={<Presentation />} />
          <Route path="/c/:conversationId" element={<div>Conversation existante</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByText("Entrer dans l'application"))
    expect(await screen.findByText('Conversation existante')).toBeInTheDocument()
  })

  it('"Entrer dans l\'application" navigates to a fresh conversation when none exist', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ conversations: [] })))
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/presentation']}>
        <Routes>
          <Route path="/presentation" element={<Presentation />} />
          <Route path="/new" element={<div>Nouvelle conversation</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByText("Entrer dans l'application"))
    expect(await screen.findByText('Nouvelle conversation')).toBeInTheDocument()
  })
})
