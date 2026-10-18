import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Composer } from './Composer'
import { defaultFilterState } from '../state/retrievalFilter'

// jsdom does no layout, so scrollHeight is stubbed: it stands in for the
// content height the browser would measure.
function renderComposer() {
  const onSubmit = vi.fn()
  render(
    <Composer
      onSubmit={onSubmit}
      filterState={defaultFilterState(1889, 1934)}
      onFilterStateChange={() => {}}
    />,
  )
  const textarea = screen.getByPlaceholderText("Posez une question sur l'œuvre de Bergson…") as HTMLTextAreaElement
  let contentHeight = 20
  Object.defineProperty(textarea, 'scrollHeight', { configurable: true, get: () => contentHeight })
  return { textarea, onSubmit, setContentHeight: (h: number) => (contentHeight = h) }
}

describe('Composer auto height', () => {
  it('grows the textarea to its content height as the question gets longer', async () => {
    const user = userEvent.setup()
    const { textarea, setContentHeight } = renderComposer()
    setContentHeight(60)
    await user.type(textarea, 'Une longue question')
    expect(textarea.style.height).toBe('60px')
  })

  it('shrinks back once the question is submitted', async () => {
    const user = userEvent.setup()
    const { textarea, onSubmit, setContentHeight } = renderComposer()
    setContentHeight(60)
    await user.type(textarea, 'Une longue question')
    setContentHeight(20)
    await user.keyboard('{Enter}')
    expect(onSubmit).toHaveBeenCalledWith('Une longue question')
    expect(textarea.style.height).toBe('20px')
  })
})
