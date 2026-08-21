import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ChunkRail } from './ChunkRail'
import { TurnUiProvider } from '../state/turnUi'
import type { ChunkResult } from '../api/types'

const chunk: ChunkResult = {
  chunk_id: 'W_c1',
  work_id: 'W',
  section_path: '',
  paragraph_ids: [],
  page_start: { number: null, display: '' },
  page_end: { number: null, display: '' },
  text: 'Un passage.',
  score: 0.5,
}

function renderRail() {
  return render(
    <TurnUiProvider>
      <MemoryRouter>
        <ChunkRail chunks={[chunk]} turnId={1} conversationId={1} />
      </MemoryRouter>
    </TurnUiProvider>,
  )
}

describe('ChunkRail', () => {
  it('starts included by default and toggles to excluded on click', async () => {
    const user = userEvent.setup()
    renderRail()

    const card = screen.getByTestId('chunk-card-W_c1')
    expect(card).toHaveAttribute('data-included', 'true')
    expect(screen.getByText('Inclus')).toBeInTheDocument()

    await user.click(screen.getByText('Exclure'))

    expect(card).toHaveAttribute('data-included', 'false')
    expect(screen.getByText('Exclu')).toBeInTheDocument()
    expect(screen.getByText('Inclure')).toBeInTheDocument()
  })
})
