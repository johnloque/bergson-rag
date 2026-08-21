// Deliberately not styled as a chat bubble (no bubble background, no
// right-alignment): each turn is an independent retrieve+generate cycle,
// not a message in a remembered dialogue (docs/ROADMAP.md, Sprint 8
// addendum — no cross-turn context). A plain labeled heading avoids
// implying otherwise.
export function QueryBubble({ query }: { query: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ink-3)' }}>
        Question
      </span>
      <p className="text-[15px] font-medium" style={{ color: 'var(--ink)' }}>
        {query}
      </p>
    </div>
  )
}
