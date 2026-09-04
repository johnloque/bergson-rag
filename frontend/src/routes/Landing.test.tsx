import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Landing } from './Landing'

describe('Landing', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ conversations: [] }) })),
    )
  })

  it('shows once per session and is skipped on a second render in the same session', async () => {
    const { unmount } = render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Commencer')).toBeInTheDocument()
    unmount()

    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>,
    )
    expect(screen.queryByText('Commencer')).not.toBeInTheDocument()
  })

  it('"Commencer" navigates to the Presentation screen, not directly into the app', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/presentation" element={<div>Écran de présentation</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(await screen.findByText('Commencer'))
    expect(await screen.findByText('Écran de présentation')).toBeInTheDocument()
  })
})
