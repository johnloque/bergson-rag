import { useState, type CSSProperties, type ReactNode } from 'react'
import { IconChevronDown, IconChevronUp } from '@tabler/icons-react'

interface DisclosureProps {
  /** Always-visible content the chevron sits next to (a label, a title —
   * whatever the caller's row is built around). */
  trigger: ReactNode
  /** Noun phrase describing what `children` discloses, turned into the
   * toggle's aria-label ("Afficher <phrase>" / "Masquer <phrase>") — same
   * phrasing rule every chevron toggle in this project already follows. */
  expandLabel: string
  /** Which side of `trigger` the chevron button sits on. Default 'trailing'
   * (the original StepLine/ConsideredSourceEntry placement); Sources.tsx's
   * anthology rows use 'leading' per the approved mockup. */
  chevronPosition?: 'leading' | 'trailing'
  chevronSize?: number
  defaultExpanded?: boolean
  rowClassName?: string
  rowStyle?: CSSProperties
  contentClassName?: string
  'data-testid'?: string
  contentTestId?: string
  children: ReactNode
}

// Shared chevron-toggle expand/collapse interaction — extracted from
// StepLine.tsx's original inline implementation once a third independent
// copy of the same interaction was about to be written for
// routes/Sources.tsx (docs/frontend.md's "answer display improvements"
// addendum already reused StepLine's own version once, for the generation
// step's included-chunks list; ConsideredSourceEntry.tsx had grown its own
// second, slightly-different copy for the per-work nested-texts toggle).
// Both are refactored onto this component below; TurnCard.tsx's "N versions
// précédentes" toggle is a materially different affordance (the entire
// label is the button, not an icon next to static text) and is left as is.
export function Disclosure({
  trigger,
  expandLabel,
  chevronPosition = 'trailing',
  chevronSize = 14,
  defaultExpanded = false,
  rowClassName = 'flex items-center gap-1',
  rowStyle,
  contentClassName,
  'data-testid': testId,
  contentTestId,
  children,
}: DisclosureProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  const buttonStyle: CSSProperties = { color: 'var(--ink-3)' }
  const toggle = (
    <button
      type="button"
      onClick={() => setExpanded((e) => !e)}
      aria-expanded={expanded}
      aria-label={expanded ? `Masquer ${expandLabel}` : `Afficher ${expandLabel}`}
      data-testid={testId}
      className="flex items-center rounded p-0.5"
      style={buttonStyle}
    >
      {expanded ? <IconChevronUp size={chevronSize} /> : <IconChevronDown size={chevronSize} />}
    </button>
  )

  return (
    <div className="flex flex-col gap-1.5">
      <div className={rowClassName} style={rowStyle}>
        {chevronPosition === 'leading' && toggle}
        {trigger}
        {chevronPosition === 'trailing' && toggle}
      </div>
      {expanded && (
        <div className={contentClassName} data-testid={contentTestId}>
          {children}
        </div>
      )}
    </div>
  )
}
