interface WordmarkProps {
  size?: number
  color?: string
}

// Georgia serif, uppercase, letter-spaced, weight 500 — reserved
// exclusively for this wordmark (docs/ROADMAP.md, Sprint 8 design tokens).
export function Wordmark({ size = 34, color = 'var(--ink)' }: WordmarkProps) {
  return (
    <div
      className="font-wordmark leading-[1.15] font-medium uppercase"
      style={{ fontSize: size, letterSpacing: size >= 28 ? '4px' : '2.5px', color }}
    >
      <div>Bergson</div>
      <div>RAG</div>
    </div>
  )
}
