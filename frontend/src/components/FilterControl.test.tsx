import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FilterControl } from './FilterControl'
import { WORK_YEAR_RANGE } from '../lib/works'
import { defaultFilterState, type RetrievalFilterState } from '../state/retrievalFilter'

function ControlledFilterControl() {
  const [state, setState] = useState<RetrievalFilterState>(() =>
    defaultFilterState(WORK_YEAR_RANGE.min, WORK_YEAR_RANGE.max),
  )
  return <FilterControl state={state} onChange={setState} />
}

async function openPanel() {
  const user = userEvent.setup()
  render(<ControlledFilterControl />)
  await user.click(screen.getByRole('button', { name: 'Filtrer les sources' }))
  return user
}

describe('FilterControl — active-filter indicator', () => {
  it('is absent by default', async () => {
    render(<ControlledFilterControl />)
    expect(screen.queryByTestId('filter-active-indicator')).not.toBeInTheDocument()
  })

  it('appears once a work is unchecked, and disappears once it is re-checked', async () => {
    const user = await openPanel()

    await user.click(screen.getByLabelText(/Le rire/))
    expect(screen.getByTestId('filter-active-indicator')).toBeInTheDocument()

    await user.click(screen.getByLabelText(/Le rire/))
    expect(screen.queryByTestId('filter-active-indicator')).not.toBeInTheDocument()
  })

  it('appears once the slider is touched, and disappears once "Réinitialiser" is used', async () => {
    const user = await openPanel()

    fireEvent.change(screen.getByLabelText('Année de début'), { target: { value: '1900' } })
    expect(screen.getByTestId('filter-active-indicator')).toBeInTheDocument()

    await user.click(screen.getByText('Réinitialiser les filtres'))
    expect(screen.queryByTestId('filter-active-indicator')).not.toBeInTheDocument()
  })
})

describe('FilterControl — work checklist', () => {
  it('starts with all 8 works checked', async () => {
    await openPanel()
    const checkboxes = screen.getAllByRole('checkbox')
    expect(checkboxes).toHaveLength(8)
    expect(checkboxes.every((cb) => (cb as HTMLInputElement).checked)).toBe(true)
  })
})

describe('FilterControl — chronological slider', () => {
  it('moving the start handle past the end handle clamps to the end value, not past it', async () => {
    await openPanel()
    fireEvent.change(screen.getByLabelText('Année de fin'), { target: { value: '1910' } })
    fireEvent.change(screen.getByLabelText('Année de début'), { target: { value: '1934' } })
    expect(screen.getByText('Période (1910–1910)')).toBeInTheDocument()
  })

  // Regression for the overlap bug: the upper-bound handle used to always
  // sit on top (fixed DOM order), so once the two handles landed on the
  // same value the lower-bound handle became permanently unreachable.
  // Which handle is on top now tracks pointer proximity (see
  // handleTrackPointerMove in FilterControl.tsx) so that whichever side of
  // the shared thumb the pointer approaches from is the one that ends up
  // grabbable — combined with the `.dual-range` pointer-events rule in
  // index.css, which restricts each input's hit area to its own thumb.
  it('raises whichever handle the pointer is closer to, so a handle stuck under the other stays reachable', async () => {
    await openPanel()
    const startInput = screen.getByLabelText('Année de début')
    const endInput = screen.getByLabelText('Année de fin')
    const track = screen.getByTestId('date-range-track')
    track.getBoundingClientRect = () =>
      ({ left: 0, right: 200, width: 200, top: 0, bottom: 0, height: 0, x: 0, y: 0, toJSON() {} }) as DOMRect

    // Collapse both handles onto the same middle value, mirroring the
    // reported repro of "both handles near each other".
    fireEvent.change(endInput, { target: { value: '1910' } })
    fireEvent.change(startInput, { target: { value: '1910' } })

    // Hovering toward the low end of the track, over the shared thumb,
    // should surface the start (lower-bound) handle.
    fireEvent.mouseMove(track, { clientX: 10 })
    expect(startInput).toHaveStyle({ zIndex: 2 })
    expect(endInput).toHaveStyle({ zIndex: 1 })

    // Hovering toward the high end should surface the end handle instead.
    fireEvent.mouseMove(track, { clientX: 190 })
    expect(startInput).toHaveStyle({ zIndex: 1 })
    expect(endInput).toHaveStyle({ zIndex: 2 })
  })
})

describe('FilterControl — mode toggle', () => {
  it('defaults to "Publication" pressed and switches to "Texte" on click', async () => {
    const user = await openPanel()
    expect(screen.getByRole('button', { name: 'Publication' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Texte' })).toHaveAttribute('aria-pressed', 'false')

    await user.click(screen.getByRole('button', { name: 'Texte' }))

    expect(screen.getByRole('button', { name: 'Texte' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Publication' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('shows a hint that it only affects the two anthology works', async () => {
    await openPanel()
    expect(screen.getByText(/L'énergie spirituelle.*La Pensée et le Mouvant/)).toBeInTheDocument()
  })
})
