import { useLayoutEffect, useRef, useState } from 'react'
import { IconSend } from '@tabler/icons-react'
import { FilterControl } from './FilterControl'
import type { RetrievalFilterState } from '../state/retrievalFilter'

interface ComposerProps {
  onSubmit: (query: string) => void
  disabled?: boolean
  filterState: RetrievalFilterState
  onFilterStateChange: (updater: (prev: RetrievalFilterState) => RetrievalFilterState) => void
}

export function Composer({ onSubmit, disabled, filterState, onFilterStateChange }: ComposerProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Grow the textarea with its content, so a multi-line question stays
  // fully visible: `rows={1}` alone keeps it one line tall forever. Reset to
  // `auto` first so the height also shrinks back (after deleting lines, or
  // on submit); `max-h-40` caps the growth, past which it scrolls.
  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [value])

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
  }

  return (
    <div
      className="flex items-end gap-2 rounded-xl p-2"
      style={{ background: 'var(--paper-2)', border: '0.5px solid var(--hairline)' }}
    >
      <FilterControl state={filterState} onChange={onFilterStateChange} disabled={disabled} />
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
        placeholder="Posez une question sur l'œuvre de Bergson…"
        rows={1}
        disabled={disabled}
        className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
        style={{ color: 'var(--ink)' }}
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !value.trim()}
        aria-label="Envoyer"
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white disabled:opacity-50"
        style={{ background: 'var(--red)' }}
      >
        <IconSend size={16} />
      </button>
    </div>
  )
}
