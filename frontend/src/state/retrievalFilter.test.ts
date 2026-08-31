import { describe, expect, it } from 'vitest'
import { ALL_WORK_IDS } from '../lib/works'
import { defaultFilterState, isFilterActive, toRetrieveFilterParams } from './retrievalFilter'

const MIN_YEAR = 1888
const MAX_YEAR = 1934

describe('retrievalFilter — default state', () => {
  it('omits both work_ids and date_range — no filter, not an explicit all-8 list', () => {
    const state = defaultFilterState(MIN_YEAR, MAX_YEAR)
    expect(isFilterActive(state)).toBe(false)
    expect(toRetrieveFilterParams(state)).toEqual({})
  })
})

describe('retrievalFilter — unchecking works', () => {
  it('sends only the checked work_ids once one is unchecked', () => {
    const state = defaultFilterState(MIN_YEAR, MAX_YEAR)
    state.checkedWorkIds.delete('1900_R')
    expect(isFilterActive(state)).toBe(true)
    const params = toRetrieveFilterParams(state)
    expect(params.work_ids).toEqual(ALL_WORK_IDS.filter((id) => id !== '1900_R'))
    expect(params.date_range).toBeUndefined()
  })

  it('sends an explicit empty list when every work is unchecked (deliberately matches nothing)', () => {
    const state = defaultFilterState(MIN_YEAR, MAX_YEAR)
    state.checkedWorkIds.clear()
    const params = toRetrieveFilterParams(state)
    expect(params.work_ids).toEqual([])
  })
})

describe('retrievalFilter — moving the slider', () => {
  it('sends date_range with the currently-selected mode once touched', () => {
    const state = defaultFilterState(MIN_YEAR, MAX_YEAR)
    state.dateTouched = true
    state.startYear = 1900
    state.endYear = 1920
    state.mode = 'text'
    const params = toRetrieveFilterParams(state)
    expect(params.date_range).toEqual({ start: 1900, end: 1920, mode: 'text' })
    expect(params.work_ids).toBeUndefined()
  })

  it('still sends date_range if touched but dragged back to the full span', () => {
    const state = defaultFilterState(MIN_YEAR, MAX_YEAR)
    state.dateTouched = true
    const params = toRetrieveFilterParams(state)
    expect(params.date_range).toEqual({ start: MIN_YEAR, end: MAX_YEAR, mode: 'publication' })
  })

  it('defaults mode to "publication" until explicitly toggled', () => {
    const state = defaultFilterState(MIN_YEAR, MAX_YEAR)
    expect(state.mode).toBe('publication')
  })
})

describe('retrievalFilter — combined filters', () => {
  it('sends both work_ids and date_range together when both are set', () => {
    const state = defaultFilterState(MIN_YEAR, MAX_YEAR)
    state.checkedWorkIds.delete('1919_ES')
    state.dateTouched = true
    state.startYear = 1901
    state.endYear = 1913
    state.mode = 'text'
    expect(toRetrieveFilterParams(state)).toEqual({
      work_ids: ALL_WORK_IDS.filter((id) => id !== '1919_ES'),
      date_range: { start: 1901, end: 1913, mode: 'text' },
    })
  })
})
