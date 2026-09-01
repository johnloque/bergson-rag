// docs/ROADMAP.md, Sprint 12: the chunk rail/detail cards and the answer
// card's included-chunks bullet list must render the exact same citation
// string for the same chunk — both call lib/citation.ts's formatCitation,
// but this test proves it by comparing the two components' actual
// rendered output (via a shared data-testid="chunk-citation"), not just
// asserting each one "looks reasonable" against formatCitation in
// isolation (lib/citation.test.ts already covers that).
import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ChunkRail } from './ChunkRail'
import { GenerationBlock } from './GenerationBlock'
import { formatCitation } from '../lib/citation'
import { TurnUiProvider } from '../state/turnUi'
import type { ChunkResult } from '../api/types'
import type { GenerationEntry } from '../state/useTurnController'

// Anthology work, paragraph resolving to a specific individually-dated
// text — the richest of the three citation shapes, so a divergence
// between the two call sites would be most visible here.
const CHUNK: ChunkResult = {
  chunk_id: '1919_ES_c160',
  work_id: '1919_ES',
  section_path: '',
  paragraph_ids: ['1919_ES_p160'],
  page_start: { number: null, display: '' },
  page_end: { number: null, display: '' },
  text: 'Un passage sur l’effort intellectuel.',
  score: 0.8,
}

function renderRail() {
  return render(
    <TurnUiProvider>
      <MemoryRouter>
        <ChunkRail chunks={[CHUNK]} turnId={1} conversationId={1} />
      </MemoryRouter>
    </TurnUiProvider>,
  )
}

const generationEntry: GenerationEntry = {
  generationId: 1,
  chunkIds: [CHUNK.chunk_id],
  state: 'done',
  answer: `Réponse [${CHUNK.chunk_id}].`,
  model: 'test-model',
  evaluation: null,
  evaluationStatus: 'idle',
  revealed: true,
}

function renderGenerationBlock() {
  return render(
    <GenerationBlock
      entry={generationEntry}
      isFirst
      chunks={[CHUNK]}
      onReveal={() => {}}
      onEvaluate={() => {}}
    />,
  )
}

describe('citation format — same string at both call sites', () => {
  it('the chunk rail card and the answer bullet list render an identical citation for the same chunk', async () => {
    const user = userEvent.setup()
    const expected = formatCitation(CHUNK)

    renderRail()
    const railCitation = screen.getByTestId('chunk-citation')
    expect(railCitation).toHaveTextContent(expected)

    renderGenerationBlock()
    const toggle = screen.getByRole('button', { name: 'Afficher les passages inclus dans la génération' })
    await user.click(toggle)
    const list = screen.getByTestId('included-chunks')
    const bulletCitation = within(list).getByTestId('chunk-citation')
    expect(bulletCitation).toHaveTextContent(expected)

    // Direct equality between the two call sites' actual rendered output —
    // not two independent assertions against the shared function.
    expect(bulletCitation.textContent).toBe(railCitation.textContent)
  })
})
