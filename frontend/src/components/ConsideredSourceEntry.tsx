import { useState } from 'react'
import { IconChevronDown, IconChevronUp } from '@tabler/icons-react'
import type { ConsideredWorkEntry } from '../lib/retrievalScope'

interface ConsideredSourceEntryProps {
  entry: ConsideredWorkEntry
}

// One row of the "sources considered" list (components/TurnCard.tsx),
// nested under the "Recherche des passages pertinents" step's own chevron
// (lib/retrievalScope.ts, feat/retrieval-filter-ui). `entry.texts` is only
// ever set for an anthology work (1919_ES/1934_PM) under "text"-mode
// date-range filtering — the individual dated texts that actually fell in
// range. That sub-list used to render unconditionally as soon as the outer
// list was expanded, with no visible affordance hinting it was there;
// now it sits behind its own small chevron next to the work's title,
// collapsed by default, so the user has a clear signal that this work's
// inclusion was narrowed to specific texts and can drill into which ones.
export function ConsideredSourceEntry({ entry }: ConsideredSourceEntryProps) {
  const [expanded, setExpanded] = useState(false)
  const hasTexts = entry.texts !== undefined && entry.texts.length > 0

  return (
    <li>
      <div className="flex items-center gap-1">
        {/* Bold + a touch darker than the (lighter, regular-weight) nested
            texts below — the parent work needs to read as a clearly
            different list level, not just an indented continuation of it. */}
        <span className="font-semibold" style={{ color: 'var(--ink-2)' }}>
          {entry.title} ({entry.year})
        </span>
        {hasTexts && (
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            aria-expanded={expanded}
            aria-label={
              expanded
                ? `Masquer les textes datés pris en compte pour ${entry.title}`
                : `Afficher les textes datés pris en compte pour ${entry.title}`
            }
            className="flex items-center rounded p-0.5"
            style={{ color: 'var(--ink-3)' }}
          >
            {expanded ? <IconChevronUp size={12} /> : <IconChevronDown size={12} />}
          </button>
        )}
      </div>
      {hasTexts && expanded && (
        <ul className="mt-1.5 flex flex-col gap-1.5 pl-4">
          {entry.texts!.map((text) => (
            <li key={text.title}>
              {text.title} ({text.year})
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}
