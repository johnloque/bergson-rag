import type { ConsideredWorkEntry } from '../lib/retrievalScope'
import { Disclosure } from './Disclosure'

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
  const hasTexts = entry.texts !== undefined && entry.texts.length > 0

  // Bold + a touch darker than the (lighter, regular-weight) nested texts
  // below — the parent work needs to read as a clearly different list
  // level, not just an indented continuation of it.
  const title = (
    <span className="font-semibold" style={{ color: 'var(--ink-2)' }}>
      {entry.title} ({entry.year})
    </span>
  )

  if (!hasTexts) {
    return (
      <li>
        <div className="flex items-center gap-1">{title}</div>
      </li>
    )
  }

  return (
    <li>
      <Disclosure
        trigger={title}
        expandLabel={`les textes datés pris en compte pour ${entry.title}`}
        chevronSize={12}
      >
        <ul className="mt-1.5 flex flex-col gap-1.5 pl-4">
          {entry.texts!.map((text) => (
            <li key={text.title}>
              {text.title} ({text.year})
            </li>
          ))}
        </ul>
      </Disclosure>
    </li>
  )
}
