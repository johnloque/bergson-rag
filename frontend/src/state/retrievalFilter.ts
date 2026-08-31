// Client-owned filter state behind the chat bar's filter control
// (components/FilterControl.tsx). Deliberately not a persisted "session
// filter" (docs/ROADMAP.md, Sprint 12 filter UI, consistent with Sprint 8's
// no-cross-turn-context design): this is plain in-memory React state,
// snapshotted into a /retrieve request at the moment a query is submitted
// (routes/Conversation.tsx), never threaded into the backend/conversation
// model itself. It is intentionally sticky across turns within one browser
// session (not reset on every submit) — the filter control's active-filter
// indicator exists precisely so a filter set on an earlier turn is never
// silently forgotten while composing the next one.

import type { DateRange, DateRangeMode } from '../api/types'
import { ALL_WORK_IDS } from '../lib/works'

export interface RetrievalFilterState {
  checkedWorkIds: Set<string>
  // Whether the user has ever moved either slider handle this session —
  // distinguishes "never touched" (omit date_range) from "touched but
  // ended up back at the full span" (still sent; see toRetrieveFilterParams).
  dateTouched: boolean
  startYear: number
  endYear: number
  mode: DateRangeMode
}

export function defaultFilterState(minYear: number, maxYear: number): RetrievalFilterState {
  return {
    checkedWorkIds: new Set(ALL_WORK_IDS),
    dateTouched: false,
    startYear: minYear,
    endYear: maxYear,
    mode: 'publication',
  }
}

// Whether the current state deviates from the "no filter" default — drives
// the filter control's badge/dot indicator.
export function isFilterActive(state: RetrievalFilterState): boolean {
  return state.checkedWorkIds.size !== ALL_WORK_IDS.length || state.dateTouched
}

export interface RetrieveFilterParams {
  work_ids?: string[]
  date_range?: DateRange
}

// Builds the additive /retrieve request fields — omits work_ids entirely
// when nothing has been unchecked (never sends an explicit all-8 list) and
// omits date_range entirely when the slider has never been touched,
// matching /retrieve's documented "omitted = unfiltered" contract
// (docs/backend_api.md) rather than an explicit full-corpus default.
export function toRetrieveFilterParams(state: RetrievalFilterState): RetrieveFilterParams {
  const params: RetrieveFilterParams = {}
  if (state.checkedWorkIds.size !== ALL_WORK_IDS.length) {
    params.work_ids = ALL_WORK_IDS.filter((id) => state.checkedWorkIds.has(id))
  }
  if (state.dateTouched) {
    params.date_range = { start: state.startYear, end: state.endYear, mode: state.mode }
  }
  return params
}
