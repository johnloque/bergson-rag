import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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
})
