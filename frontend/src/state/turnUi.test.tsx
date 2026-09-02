import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import type { ChunkNeighborSummary } from '../api/types'
import { MAX_INCLUDED_CHUNKS, TurnUiProvider, useTurnUi } from './turnUi'

function wrapper({ children }: { children: ReactNode }) {
  return <TurnUiProvider>{children}</TurnUiProvider>
}

function neighbor(chunkId: string, overrides: Partial<ChunkNeighborSummary> = {}): ChunkNeighborSummary {
  return {
    chunk_id: chunkId,
    work_id: 'W',
    section_id: 'W_s1',
    section_path: '',
    paragraph_ids: [],
    page_start: { number: null, display: '' },
    page_end: { number: null, display: '' },
    text: 'Un passage voisin.',
    ...overrides,
  }
}

// docs/ROADMAP.md, Sprint 12 `feat/chunk-neighbor-expansion`: turnUi.tsx is
// the single shared source of truth for inclusion state across Screen 3
// and Screen 4, now covering neighbor-origin chunks (state/turnUi.tsx's
// `neighbors` map) alongside the pre-existing rail-origin `included` map —
// these tests exercise the reducer directly rather than through a
// particular component, since both ChunkRail and ChunkDetail dispatch into
// the exact same actions.
describe('turnUi — neighbor-origin inclusion', () => {
  it('is not included, and not retrieved, before it has ever been added', () => {
    const { result } = renderHook(() => useTurnUi(), { wrapper })
    act(() => result.current.initTurn(1, ['c1', 'c2', 'c3', 'c4', 'c5']))

    expect(result.current.getIncluded(1, 'neighbor_c1')).toBe(false)
    expect(result.current.isRetrieved(1, 'neighbor_c1')).toBe(false)
  })

  it('toggling a neighbor chunk on includes it and counts it toward the shared cap', () => {
    const { result } = renderHook(() => useTurnUi(), { wrapper })
    act(() => result.current.initTurn(1, ['c1', 'c2', 'c3', 'c4', 'c5']))
    // Default selection: top 3 of the 5 retrieved chunks.
    expect(result.current.getIncludedCount(1)).toBe(3)

    act(() => result.current.toggleNeighborChunk(1, neighbor('n1')))

    expect(result.current.getIncluded(1, 'n1')).toBe(true)
    expect(result.current.getIncludedCount(1)).toBe(4)
    expect(result.current.getNeighborChunks(1).map((c) => c.chunk_id)).toEqual(['n1'])
  })

  it('toggling an included neighbor chunk off REMOVES it entirely, not just marks it excluded', () => {
    const { result } = renderHook(() => useTurnUi(), { wrapper })
    act(() => result.current.initTurn(1, ['c1', 'c2', 'c3', 'c4', 'c5']))
    act(() => result.current.toggleNeighborChunk(1, neighbor('n1')))
    expect(result.current.getNeighborChunks(1)).toHaveLength(1)

    act(() => result.current.toggleNeighborChunk(1, neighbor('n1')))

    expect(result.current.getNeighborChunks(1)).toHaveLength(0)
    expect(result.current.getIncluded(1, 'n1')).toBe(false)
    expect(result.current.getIncludedCount(1)).toBe(3)
  })

  it('blocks a neighbor inclusion once the combined rail+neighbor count is at the cap', () => {
    const { result } = renderHook(() => useTurnUi(), { wrapper })
    act(() => result.current.initTurn(1, ['c1', 'c2', 'c3', 'c4', 'c5']))
    // 3 included by default; include 2 more rail-origin chunks to reach 5.
    act(() => result.current.toggleChunk(1, 'c4'))
    act(() => result.current.toggleChunk(1, 'c5'))
    expect(result.current.getIncludedCount(1)).toBe(MAX_INCLUDED_CHUNKS)

    act(() => result.current.toggleNeighborChunk(1, neighbor('n1')))

    expect(result.current.getIncludedCount(1)).toBe(MAX_INCLUDED_CHUNKS)
    expect(result.current.getNeighborChunks(1)).toHaveLength(0)
  })

  it('freeing a rail-origin slot lets a neighbor inclusion through', () => {
    const { result } = renderHook(() => useTurnUi(), { wrapper })
    act(() => result.current.initTurn(1, ['c1', 'c2', 'c3', 'c4', 'c5']))
    act(() => result.current.toggleChunk(1, 'c4'))
    act(() => result.current.toggleChunk(1, 'c5'))
    act(() => result.current.toggleChunk(1, 'c1')) // free a slot

    act(() => result.current.toggleNeighborChunk(1, neighbor('n1')))

    expect(result.current.getIncludedCount(1)).toBe(MAX_INCLUDED_CHUNKS)
    expect(result.current.getIncluded(1, 'n1')).toBe(true)
  })

  it('isRetrieved distinguishes a rail-origin chunk_id from a genuine neighbor', () => {
    const { result } = renderHook(() => useTurnUi(), { wrapper })
    act(() => result.current.initTurn(1, ['c1', 'c2', 'c3']))

    expect(result.current.isRetrieved(1, 'c1')).toBe(true)
    expect(result.current.isRetrieved(1, 'n1')).toBe(false)
  })

  it('two turns keep independent neighbor sets', () => {
    const { result } = renderHook(() => useTurnUi(), { wrapper })
    act(() => result.current.initTurn(1, ['c1']))
    act(() => result.current.initTurn(2, ['c1']))

    act(() => result.current.toggleNeighborChunk(1, neighbor('n1')))

    expect(result.current.getNeighborChunks(1)).toHaveLength(1)
    expect(result.current.getNeighborChunks(2)).toHaveLength(0)
  })
})
