import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Sidebar } from './Sidebar'

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body })
}

function renderSidebar(extraRoutes: ReactNode = null) {
  const client = new QueryClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/new']}>
        <Routes>
          <Route path="/new" element={<Sidebar />} />
          {extraRoutes}
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Sidebar', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ conversations: [] })))
  })

  it('clicking the wordmark navigates to Presentation, never to Landing', async () => {
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/new']}>
          <Routes>
            <Route path="/new" element={<Sidebar />} />
            <Route path="/presentation" element={<div>Écran de présentation</div>} />
            <Route path="/" element={<div>Écran d'accueil</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    await user.click(screen.getByLabelText('Présentation de Bergson-RAG'))
    expect(await screen.findByText('Écran de présentation')).toBeInTheDocument()
    expect(screen.queryByText("Écran d'accueil")).not.toBeInTheDocument()
  })

  it('resizes via the drag handle and persists the width across a reload', async () => {
    const { unmount } = renderSidebar()
    const handle = screen.getByTestId('sidebar-resize-handle')

    fireEvent.mouseDown(handle)
    fireEvent.mouseMove(window, { clientX: 300 })
    fireEvent.mouseUp(window)

    expect(localStorage.getItem('bergson_sidebar_width')).toBe('300')
    unmount()

    // Reload: a fresh mount reads the persisted width back.
    renderSidebar()
    const aside = screen.getByTestId('sidebar-resize-handle').parentElement as HTMLElement
    expect(aside.style.width).toBe('300px')
  })

  it('both collapsible sections and the pinned Réglages entry expand/collapse independently', async () => {
    const user = userEvent.setup()
    renderSidebar()

    const guideToggle = screen.getByRole('button', { name: /Guide & Sources/ })
    const conversationsToggle = screen.getByRole('button', { name: /Conversations/ })
    const settingsToggle = screen.getByRole('button', { name: /Réglages/ })

    // All start visible except the Réglages placeholder note, which starts collapsed.
    // "Nouvelle conversation" sits between the two menus, outside both, so it is
    // always visible regardless of their expand/collapse state.
    expect(screen.getByText('Présentation')).toBeInTheDocument()
    expect(screen.getByText("Guide d'utilisation")).toBeInTheDocument()
    expect(screen.getByText('Nouvelle conversation')).toBeInTheDocument()
    expect(screen.queryByText('Aucun réglage disponible pour le moment.')).not.toBeInTheDocument()

    // Collapsing Guide & Sources doesn't touch Conversations, Réglages, or the button.
    await user.click(guideToggle)
    expect(screen.queryByText('Présentation')).not.toBeInTheDocument()
    expect(screen.queryByText("Guide d'utilisation")).not.toBeInTheDocument()
    expect(screen.getByText('Nouvelle conversation')).toBeInTheDocument()

    // Expanding Réglages doesn't re-expand Guide & Sources.
    await user.click(settingsToggle)
    expect(screen.getByText('Aucun réglage disponible pour le moment.')).toBeInTheDocument()
    expect(screen.queryByText("Guide d'utilisation")).not.toBeInTheDocument()

    // Collapsing Conversations leaves Réglages open and the button visible.
    await user.click(conversationsToggle)
    expect(screen.getByText('Nouvelle conversation')).toBeInTheDocument()
    expect(screen.getByText('Aucun réglage disponible pour le moment.')).toBeInTheDocument()
  })

  it('conversation list behavior is unchanged: navigates to a conversation on click', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({
          conversations: [{ conversation_id: 3, created_at: 'now', title: 'Une conversation', first_query: 'Q' }],
        }),
      ),
    )
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/new']}>
          <Routes>
            <Route path="/new" element={<Sidebar />} />
            <Route path="/c/:conversationId" element={<div>Conversation ouverte</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    await user.click(await screen.findByText('Une conversation'))
    expect(await screen.findByText('Conversation ouverte')).toBeInTheDocument()
  })
})
