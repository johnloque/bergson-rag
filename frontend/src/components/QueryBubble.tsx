export function QueryBubble({ query }: { query: string }) {
  return (
    <div className="flex justify-end">
      <div
        className="max-w-[70%] rounded-xl px-4 py-2.5 text-sm"
        style={{ background: 'var(--paper-2)', color: 'var(--ink)' }}
      >
        {query}
      </div>
    </div>
  )
}
