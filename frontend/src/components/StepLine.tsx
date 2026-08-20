import { IconCheck, IconLoader2 } from '@tabler/icons-react'

interface StepLineProps {
  label: string
  done: boolean
}

// A single accumulating processing-step row (docs/ROADMAP.md, Sprint 8,
// Screen 3) — checkmark once done, spinner while active. Callers place it
// at the point in the flow where that step actually happens, rather than
// bundling all steps into one block.
export function StepLine({ label, done }: StepLineProps) {
  return (
    <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--ink-2)' }}>
      {done ? (
        <IconCheck size={15} style={{ color: 'var(--gray-dark)' }} />
      ) : (
        <IconLoader2 size={15} className="animate-spin" style={{ color: 'var(--ink-3)' }} />
      )}
      <span>{label}</span>
    </div>
  )
}
