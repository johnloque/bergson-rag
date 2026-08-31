import { useState, type ReactNode } from 'react'
import { IconCheck, IconChevronDown, IconChevronUp, IconLoader2, IconX } from '@tabler/icons-react'

interface StepLineProps {
  label: string
  done: boolean
  failed?: boolean
  /** Optional expandable detail (e.g. the sources a filter actually left
   * in scope, components/TurnCard.tsx) — collapsed by default. Offered as
   * soon as it's available, not gated on `done`: a turn's applied filter
   * is known and persisted the moment the request is sent
   * (src/api/persistence.py's create_turn), well before retrieval itself
   * finishes, so the detail can and should show up while the step is
   * still spinning. `null`/`undefined` renders no expand affordance at
   * all, same as omitting the prop. */
  children?: ReactNode
}

// A single accumulating processing-step row (docs/ROADMAP.md, Sprint 8,
// Screen 3) — checkmark once done, spinner while active, red X if the step
// itself errored out (e.g. evaluation provider down) so it never reads as a
// green "success" next to a red "indisponible" pill elsewhere in the card.
// Callers place it at the point in the flow where that step actually
// happens, rather than bundling all steps into one block.
export function StepLine({ label, done, failed, children }: StepLineProps) {
  const [expanded, setExpanded] = useState(false)
  const expandable = !failed && children != null

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--ink-2)' }}>
        {failed ? (
          <IconX size={15} style={{ color: 'var(--red)' }} />
        ) : done ? (
          <IconCheck size={15} style={{ color: 'var(--gray-dark)' }} />
        ) : (
          <IconLoader2 size={15} className="animate-spin" style={{ color: 'var(--ink-3)' }} />
        )}
        <span>{label}</span>
        {expandable && (
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            aria-expanded={expanded}
            aria-label={expanded ? 'Masquer les sources prises en compte' : 'Afficher les sources prises en compte'}
            className="flex items-center rounded p-0.5"
            style={{ color: 'var(--ink-3)' }}
          >
            {expanded ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
          </button>
        )}
      </div>
      {expandable && expanded && <div className="pl-[23px]">{children}</div>}
    </div>
  )
}
