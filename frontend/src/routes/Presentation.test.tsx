import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Presentation } from './Presentation'

describe('Presentation', () => {
  it('renders as plain content, no longer a standalone screen with its own entry button', () => {
    render(
      <MemoryRouter initialEntries={['/presentation']}>
        <Routes>
          <Route path="/presentation" element={<Presentation />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('Présentation')).toBeInTheDocument()
    expect(screen.queryByText("Entrer dans l'application")).not.toBeInTheDocument()
  })
})
