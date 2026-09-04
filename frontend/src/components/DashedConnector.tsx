import { IconArrowDown, IconArrowRight } from '@tabler/icons-react'

// Shared "dashed line + arrow" visual vocabulary, first established by
// PositionFilmstrip's cell-to-cell connectors (`feat/chunk-neighbor-expansion`)
// and now reused a second time by the Guide walkthrough's step spine
// (`feat/presentation-and-guide-content`) — extracted here rather than left
// inline a second time, since a third inline copy would be a real
// duplication smell.

interface DashedArrowProps {
  direction?: 'right' | 'down'
  size?: number
  className?: string
}

export function DashedArrow({ direction = 'right', size = 16, className = 'shrink-0' }: DashedArrowProps) {
  const Icon = direction === 'down' ? IconArrowDown : IconArrowRight
  return <Icon size={size} className={className} style={{ color: 'var(--ink-3)' }} aria-hidden="true" />
}

interface DashedLineProps {
  orientation?: 'vertical' | 'horizontal'
  className?: string
}

// A standalone dashed connector line, --hairline colored — the line half of
// the same vocabulary the filmstrip cells already use as a border. Used as
// a continuous spine running behind the Guide page's step sequence.
export function DashedLine({ orientation = 'vertical', className }: DashedLineProps) {
  return (
    <div
      aria-hidden="true"
      className={className}
      style={
        orientation === 'vertical'
          ? { width: 0, borderLeft: '1.5px dashed var(--hairline)' }
          : { height: 0, borderTop: '1.5px dashed var(--hairline)' }
      }
    />
  )
}
