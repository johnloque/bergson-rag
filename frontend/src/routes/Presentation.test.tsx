import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Presentation } from './Presentation'

describe('Presentation', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ conversations: [] }) })),
    )
  })

  it('renders the pull-quote and both cards', () => {
    render(
      <MemoryRouter initialEntries={['/presentation']}>
        <Routes>
          <Route path="/presentation" element={<Presentation />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('Bienvenue sur Bergson-RAG !')).toBeInTheDocument()
    expect(screen.getByText(/ne remplace pas une lecture rapprochée/)).toBeInTheDocument()
    expect(screen.getByText('Le retrieval')).toBeInTheDocument()
    expect(screen.getByText('La génération')).toBeInTheDocument()
  })

  it('"Guide d\'utilisation" navigates to the sidebar\'s guide sub-page', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/presentation']}>
        <Routes>
          <Route path="/presentation" element={<Presentation />} />
          <Route path="/guide/utilisation" element={<div>Écran du guide</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByText("Guide d'utilisation"))
    expect(await screen.findByText('Écran du guide')).toBeInTheDocument()
  })

  it('"Poser ma première question" navigates to /new, same as the sidebar\'s "Nouvelle conversation"', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/presentation']}>
        <Routes>
          <Route path="/presentation" element={<Presentation />} />
          <Route path="/new" element={<div>Nouvelle conversation</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByText('Poser ma première question'))
    expect(await screen.findByText('Nouvelle conversation')).toBeInTheDocument()
  })
})
