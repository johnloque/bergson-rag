interface AbstractGraphicProps {
  size?: number
}

// Deliberately abstract — a single curved line with two anchor dots, no
// human figure or silhouette. This was an explicit content-safety decision
// made during design (docs/ROADMAP.md, Sprint 8, Screen 1), not just an
// aesthetic one — do not add a face or recognizable portrait here.
//
// Shared between Landing (full size) and Presentation
// (`size={70}`, `feat/presentation-and-guide-content`) — one SVG, not two
// copies of the same markup.
export function AbstractGraphic({ size = 120 }: AbstractGraphicProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" aria-hidden="true">
      <path
        d="M20 85 C 35 20, 85 20, 100 55 S 70 100, 45 70"
        stroke="var(--red)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="20" cy="85" r="4" fill="var(--red)" />
      <circle cx="45" cy="70" r="4" fill="var(--red)" />
    </svg>
  )
}
