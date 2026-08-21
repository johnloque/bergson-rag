import { IconCheck, IconLoader2, IconX } from '@tabler/icons-react'

interface StepLineProps {
  label: string
  done: boolean
  failed?: boolean
}

// A single accumulating processing-step row (docs/ROADMAP.md, Sprint 8,
// Screen 3) — checkmark once done, spinner while active, red X if the step
// itself errored out (e.g. evaluation provider down) so it never reads as a
// green "success" next to a red "indisponible" pill elsewhere in the card.
// Callers place it at the point in the flow where that step actually
// happens, rather than bundling all steps into one block.
export function StepLine({ label, done, failed }: StepLineProps) {
  return (
    <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--ink-2)' }}>
      {failed ? (
        <IconX size={15} style={{ color: 'var(--red)' }} />
      ) : done ? (
        <IconCheck size={15} style={{ color: 'var(--gray-dark)' }} />
      ) : (
        <IconLoader2 size={15} className="animate-spin" style={{ color: 'var(--ink-3)' }} />
      )}
      <span>{label}</span>
    </div>
  )
}
