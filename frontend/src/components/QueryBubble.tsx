export function QueryBubble({ query }: { query: string }) {
  return (
    <div className="flex justify-end">
      <div
        className="max-w-[70%] rounded-xl px-4 py-2.5 text-sm"
        style={{ background: 'var(--paper-2)', border: '0.5px solid var(--hairline)', color: 'var(--ink)' }}
      >
        {query}
      </div>
    </div>
  )
}
