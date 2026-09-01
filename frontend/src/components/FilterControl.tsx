import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { IconFilter, IconX } from '@tabler/icons-react'
import type { DateRangeMode } from '../api/types'
import { WORK_YEAR_RANGE, WORKS } from '../lib/works'
import { defaultFilterState, isFilterActive, type RetrievalFilterState } from '../state/retrievalFilter'

interface FilterControlProps {
  state: RetrievalFilterState
  onChange: (updater: (prev: RetrievalFilterState) => RetrievalFilterState) => void
  disabled?: boolean
}

// Icon-triggered popover in the chat bar (docs/frontend.md, Sprint 12
// filter UI) rather than an always-open panel — the common case is no
// filtering at all, so the control stays a single unobtrusive icon until
// opened. The active-filter dot on the icon is what keeps a filter set on
// an earlier turn from being silently forgotten while composing the next
// one (state/retrievalFilter.ts).
export function FilterControl({ state, onChange, disabled }: FilterControlProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const trackRef = useRef<HTMLDivElement>(null)
  // Which handle sits on top of the other — matters only when they're at
  // (or very near) the same value, so the thumb the pointer is hovering
  // toward is the one that ends up grabbed on mousedown. Kept in sync by
  // handleTrackPointerMove below rather than derived from state, since the
  // browser resolves a mousedown's target from whatever is already on top
  // *before* our onChange handlers ever run.
  const [topHandle, setTopHandle] = useState<'start' | 'end'>('end')
  const active = isFilterActive(state)

  // Position of each handle as a 0–1 fraction of the track, used both to
  // paint the selected-range highlight below and to judge pointer
  // proximity in handleTrackPointerMove.
  const startPercent = (state.startYear - WORK_YEAR_RANGE.min) / (WORK_YEAR_RANGE.max - WORK_YEAR_RANGE.min)
  const endPercent = (state.endYear - WORK_YEAR_RANGE.min) / (WORK_YEAR_RANGE.max - WORK_YEAR_RANGE.min)

  function handleTrackPointerMove(event: ReactMouseEvent<HTMLDivElement>) {
    const track = trackRef.current
    if (!track) return
    const rect = track.getBoundingClientRect()
    const percent = (event.clientX - rect.left) / rect.width
    const distStart = Math.abs(percent - startPercent)
    const distEnd = Math.abs(percent - endPercent)
    if (distStart !== distEnd) {
      setTopHandle(distStart < distEnd ? 'start' : 'end')
    } else {
      // Handles coincide exactly — nothing to compare distances against,
      // so fall back to which side of the shared thumb the pointer is on.
      setTopHandle(percent < startPercent ? 'start' : 'end')
    }
  }

  useEffect(() => {
    if (!open) return
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  function toggleWork(workId: string) {
    onChange((prev) => {
      const next = new Set(prev.checkedWorkIds)
      if (next.has(workId)) next.delete(workId)
      else next.add(workId)
      return { ...prev, checkedWorkIds: next }
    })
  }

  function setStartYear(year: number) {
    onChange((prev) => ({ ...prev, dateTouched: true, startYear: Math.min(year, prev.endYear) }))
  }

  function setEndYear(year: number) {
    onChange((prev) => ({ ...prev, dateTouched: true, endYear: Math.max(year, prev.startYear) }))
  }

  function setMode(mode: DateRangeMode) {
    onChange((prev) => ({ ...prev, mode }))
  }

  function reset() {
    onChange(() => defaultFilterState(WORK_YEAR_RANGE.min, WORK_YEAR_RANGE.max))
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        aria-label="Filtrer les sources"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
        style={{
          border: '0.5px solid var(--hairline)',
          color: active ? 'var(--red)' : 'var(--ink-2)',
          background: open ? 'var(--paper-2)' : 'transparent',
        }}
      >
        <IconFilter size={16} />
        {active && (
          <span
            data-testid="filter-active-indicator"
            aria-hidden="true"
            className="absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full"
            style={{ background: 'var(--red)' }}
          />
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Filtrer les sources"
          className="absolute bottom-full left-0 z-10 mb-2 flex w-72 flex-col gap-4 rounded-xl p-4 text-sm shadow-lg"
          style={{ background: 'var(--paper)', border: '0.5px solid var(--hairline)' }}
        >
          <div className="flex items-center justify-between">
            <span className="font-medium" style={{ color: 'var(--ink)' }}>
              Filtrer les sources
            </span>
            <button
              type="button"
              aria-label="Fermer"
              onClick={() => setOpen(false)}
              style={{ color: 'var(--ink-3)' }}
            >
              <IconX size={14} />
            </button>
          </div>

          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1 text-xs font-semibold uppercase" style={{ color: 'var(--ink-3)' }}>
              Œuvres
            </legend>
            {WORKS.map((work) => (
              <label key={work.id} className="flex items-center gap-2 text-xs" style={{ color: 'var(--ink-2)' }}>
                <input
                  type="checkbox"
                  checked={state.checkedWorkIds.has(work.id)}
                  onChange={() => toggleWork(work.id)}
                />
                {work.title} ({work.year})
              </label>
            ))}
          </fieldset>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold uppercase" style={{ color: 'var(--ink-3)' }}>
              Période ({state.startYear}–{state.endYear})
            </span>
            <div
              ref={trackRef}
              data-testid="date-range-track"
              className="relative h-5"
              onMouseMove={handleTrackPointerMove}
              onTouchStart={(e) =>
                handleTrackPointerMove({ clientX: e.touches[0].clientX } as ReactMouseEvent<HTMLDivElement>)
              }
            >
              {/* Native <input type="range"> paints its own accent fill from
                  the track's start up to *its own* value — with two stacked
                  inputs that reads as "filled up to whichever handle", not
                  as the actual start–end selection. .dual-range strips that
                  native fill (index.css); these two divs draw the real
                  selection band instead. */}
              <div
                className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full"
                style={{ background: 'var(--hairline)' }}
              />
              <div
                className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full"
                style={{
                  background: 'var(--ink-2)',
                  left: `${startPercent * 100}%`,
                  right: `${(1 - endPercent) * 100}%`,
                }}
              />
              <input
                type="range"
                aria-label="Année de début"
                min={WORK_YEAR_RANGE.min}
                max={WORK_YEAR_RANGE.max}
                value={state.startYear}
                onChange={(e) => setStartYear(Number(e.target.value))}
                className="dual-range absolute inset-x-0 top-1/2 w-full -translate-y-1/2"
                style={{ zIndex: topHandle === 'start' ? 2 : 1 }}
              />
              <input
                type="range"
                aria-label="Année de fin"
                min={WORK_YEAR_RANGE.min}
                max={WORK_YEAR_RANGE.max}
                value={state.endYear}
                onChange={(e) => setEndYear(Number(e.target.value))}
                className="dual-range absolute inset-x-0 top-1/2 w-full -translate-y-1/2"
                style={{ zIndex: topHandle === 'end' ? 2 : 1 }}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-xs font-semibold uppercase" style={{ color: 'var(--ink-3)' }}>
              Mode de datation
            </span>
            <div className="flex overflow-hidden rounded-lg" style={{ border: '0.5px solid var(--hairline)' }}>
              {(['publication', 'text'] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={state.mode === mode}
                  onClick={() => setMode(mode)}
                  className="flex-1 px-2 py-1 text-xs"
                  style={{
                    background: state.mode === mode ? 'var(--paper-2)' : 'transparent',
                    color: state.mode === mode ? 'var(--ink)' : 'var(--ink-3)',
                    fontWeight: state.mode === mode ? 600 : 400,
                  }}
                >
                  {mode === 'publication' ? 'Publication' : 'Texte'}
                </button>
              ))}
            </div>
            <p className="text-[11px]" style={{ color: 'var(--ink-3)' }}>
              Ne change les résultats que pour L'énergie spirituelle (1919) et La Pensée et le Mouvant
              (1934) — identique aux 6 autres œuvres.
            </p>
          </div>

          <button
            type="button"
            onClick={reset}
            disabled={!active}
            className="self-start text-xs underline disabled:no-underline disabled:opacity-50"
            style={{ color: 'var(--ink-3)' }}
          >
            Réinitialiser les filtres
          </button>
        </div>
      )}
    </div>
  )
}
