import type { ReactNode } from 'react'
import { IconCheck, IconLoader2, IconX } from '@tabler/icons-react'
import { Disclosure } from './Disclosure'

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
  /** Noun phrase describing what `children` discloses, used in the
   * chevron's aria-label ("Afficher <phrase>" / "Masquer <phrase>") — this
   * component is reused for more than one kind of detail (the retrieval
   * step's considered sources, components/TurnCard.tsx; the generation
   * step's included chunks, components/GenerationBlock.tsx), so the label
   * must describe the one actually behind it rather than a generic/wrong
   * default. Defaults to the original retrieval-step wording for
   * backward compatibility. */
  expandLabel?: string
}

// A single accumulating processing-step row (docs/ROADMAP.md, Sprint 8,
// Screen 3) — checkmark once done, spinner while active, red X if the step
// itself errored out (e.g. evaluation provider down) so it never reads as a
// green "success" next to a red "indisponible" pill elsewhere in the card.
// Callers place it at the point in the flow where that step actually
// happens, rather than bundling all steps into one block.
export function StepLine({
  label,
  done,
  failed,
  children,
  expandLabel = 'les sources prises en compte',
}: StepLineProps) {
  const expandable = !failed && children != null

  const statusIcon = failed ? (
    <IconX size={15} style={{ color: 'var(--red)' }} />
  ) : done ? (
    <IconCheck size={15} style={{ color: 'var(--gray-dark)' }} />
  ) : (
    <IconLoader2 size={15} className="animate-spin" style={{ color: 'var(--ink-3)' }} />
  )

  if (!expandable) {
    return (
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--ink-2)' }}>
          {statusIcon}
          <span>{label}</span>
        </div>
      </div>
    )
  }

  return (
    <Disclosure
      trigger={
        <>
          {statusIcon}
          <span>{label}</span>
        </>
      }
      expandLabel={expandLabel}
      rowClassName="flex items-center gap-2 text-sm"
      rowStyle={{ color: 'var(--ink-2)' }}
      contentClassName="pl-[23px]"
    >
      {children}
    </Disclosure>
  )
}
