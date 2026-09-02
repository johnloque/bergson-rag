import { createContext, useCallback, useContext, useReducer, type ReactNode } from 'react'
import type { ChunkJudgment, ChunkNeighborSummary } from '../api/types'

// Client-side-only state (docs/ROADMAP.md, Sprint 8 "State / data flow"):
// which chunks are currently included/excluded in a turn's rail, and the
// chunk_judgments accumulated for that turn from /judge-chunk calls. Both
// stay purely local until the next /generate or /judge-chunk call sends
// them — there is no separate persistence endpoint for chunk inclusion.
// Lives in a context (not per-component state) because Screen 4 (chunk
// detail) is a separate route that toggles the same turn's inclusion state
// and adds judgments the conversation view must reflect on return.

// docs/ROADMAP.md, Sprint 12: the chunk rail now shows the top 15
// post-reranking chunks (lib/retrievalConfig.ts's CHUNK_RAIL_TOP_K),
// with only the top DEFAULT_INCLUDED_COUNT checked/included by default
// (down from every retrieved chunk) and at most MAX_INCLUDED_CHUNKS
// selectable at once. Both live here, not in components/ChunkRail.tsx,
// because this reducer is the single source of truth for inclusion state
// shared by both the chunk rail and routes/ChunkDetail.tsx's own
// Inclure/Exclure toggle — the cap has to hold regardless of which UI
// surface changed it.
export const DEFAULT_INCLUDED_COUNT = 3
export const MAX_INCLUDED_CHUNKS = 5

interface TurnUiState {
  included: Record<number, Record<string, boolean>>
  judgments: Record<number, Record<string, ChunkJudgment>>
  // Sprint 12 `feat/chunk-neighbor-expansion` additions below. A turn's
  // originally-retrieved chunk_ids (set once, at 'init') — the only way to
  // tell a rail-origin chunk from a neighbor-origin one later, since a
  // neighbor navigated to via Screen 4's filmstrip can turn out to already
  // be one of the retrieved 15 (see `neighbors` below).
  retrievedIds: Record<number, string[]>
  // Chunks included purely via neighbor exploration (Screen 4), keyed by
  // chunk_id, full record (not just a boolean) since Screen 3's rail needs
  // to render a citation for a chunk it never itself retrieved. A chunk's
  // presence here *is* its inclusion state — unlike `included` above,
  // there is no "present but excluded" entry: excluding a neighbor-origin
  // chunk removes it from this map entirely (docs/frontend.md's asymmetric
  // exclude-behavior), it never lingers as a greyed-out card.
  neighbors: Record<number, Record<string, ChunkNeighborSummary>>
}

type Action =
  | {
      type: 'init'
      turnId: number
      chunkIds: string[]
      judgments?: Record<string, ChunkJudgment>
      // Chunk-neighbor-persistence fix (docs/ROADMAP.md): the server's
      // persisted inclusion state, from GET /turns/{id} — `includedChunkIds`
      // null means never customized (apply the DEFAULT_INCLUDED_COUNT
      // default below, same as before this fix); `neighborChunks` seeds the
      // `neighbors` map so a reload restores manually-included neighbors
      // instead of losing them.
      includedChunkIds?: string[] | null
      neighborChunks?: ChunkNeighborSummary[]
    }
  | { type: 'toggle'; turnId: number; chunkId: string }
  | { type: 'toggleNeighbor'; turnId: number; chunk: ChunkNeighborSummary }
  | { type: 'judge'; turnId: number; chunkId: string; judgment: ChunkJudgment }

// Shared by the 'toggle' and 'toggleNeighbor' cap checks below — a
// neighbor-origin inclusion counts exactly the same toward the 5-chunk cap
// as a rail-origin one (docs/frontend.md), so both cases have to look at
// the same combined count rather than each enforcing their own.
function includedCountFor(state: TurnUiState, turnId: number): number {
  const retrievedIncluded = Object.values(state.included[turnId] ?? {}).filter(Boolean).length
  const neighborIncluded = Object.keys(state.neighbors[turnId] ?? {}).length
  return retrievedIncluded + neighborIncluded
}

function reducer(state: TurnUiState, action: Action): TurnUiState {
  switch (action.type) {
    case 'init': {
      const existing = state.included[action.turnId] ?? {}
      const nextIncluded = { ...existing }
      // `action.includedChunkIds` (GET /turns/{id}'s persisted state) wins
      // when given: a chunk_id is included iff it's in that list. `null`/
      // undefined (never customized server-side) falls back to the
      // original rule — top DEFAULT_INCLUDED_COUNT by rank (action.chunkIds
      // is always in the turn's reranked order, state/useTurnController.ts)
      // default to included, the rest excluded. Either way, only fills in
      // ids not already in `nextIncluded` — every chunk from a real
      // /retrieve or GET /turns/{id} response gets a concrete entry here,
      // so the `getIncluded` fallback below only ever matters for a chunk
      // this reducer has never seen, and a second initTurn call for the
      // same turnId (e.g. Screen 3 and Screen 4 mounted together) never
      // clobbers a toggle already made this session.
      const includedFromServer = action.includedChunkIds
        ? new Set(action.includedChunkIds)
        : null
      action.chunkIds.forEach((id, index) => {
        if (id in nextIncluded) return
        nextIncluded[id] = includedFromServer ? includedFromServer.has(id) : index < DEFAULT_INCLUDED_COUNT
      })
      const nextJudgments = action.judgments
        ? { ...action.judgments, ...state.judgments[action.turnId] }
        : state.judgments[action.turnId]
      return {
        ...state,
        included: { ...state.included, [action.turnId]: nextIncluded },
        judgments: { ...state.judgments, [action.turnId]: nextJudgments ?? {} },
        // Set once per turnId (a turn is only ever initTurn'd once per
        // session in practice) — this is what lets getIncluded/isRetrieved
        // tell a rail-origin chunk_id from a neighbor-origin one.
        retrievedIds:
          action.turnId in state.retrievedIds
            ? state.retrievedIds
            : { ...state.retrievedIds, [action.turnId]: action.chunkIds },
        // Same "set once per turnId" guard as retrievedIds above — a
        // second initTurn call for an already-seeded turn never clobbers
        // neighbor inclusions/exclusions already made this session.
        neighbors:
          action.turnId in state.neighbors
            ? state.neighbors
            : {
                ...state.neighbors,
                [action.turnId]: Object.fromEntries(
                  (action.neighborChunks ?? []).map((chunk) => [chunk.chunk_id, chunk]),
                ),
              },
      }
    }
    case 'toggle': {
      const existing = state.included[action.turnId] ?? {}
      const current = existing[action.chunkId] ?? true
      if (!current) {
        // About to move a chunk from excluded to included — block it once
        // MAX_INCLUDED_CHUNKS are already included, a true no-op (docs/
        // ROADMAP.md, Sprint 12: "block it with a clear indication",
        // chosen over auto-unchecking the least-recently-checked chunk).
        // Callers (components/ChunkRail.tsx, routes/ChunkDetail.tsx) also
        // disable their own "Inclure" affordance at the cap so this never
        // silently no-ops on a click that looked enabled.
        if (includedCountFor(state, action.turnId) >= MAX_INCLUDED_CHUNKS) return state
      }
      return {
        ...state,
        included: {
          ...state.included,
          [action.turnId]: { ...existing, [action.chunkId]: !current },
        },
      }
    }
    case 'toggleNeighbor': {
      const existingNeighbors = state.neighbors[action.turnId] ?? {}
      const chunkId = action.chunk.chunk_id
      if (chunkId in existingNeighbors) {
        // Included -> exclude means REMOVE entirely (docs/frontend.md): a
        // neighbor chunk was manually opted into inclusion, so opting out
        // undoes that addition — unlike a rail-origin exclusion, which
        // always leaves the card visible (it's an actual retrieved
        // candidate), a neighbor-origin card has no reason to still exist
        // once excluded.
        const rest = Object.fromEntries(
          Object.entries(existingNeighbors).filter(([id]) => id !== chunkId),
        )
        return { ...state, neighbors: { ...state.neighbors, [action.turnId]: rest } }
      }
      if (includedCountFor(state, action.turnId) >= MAX_INCLUDED_CHUNKS) return state
      return {
        ...state,
        neighbors: {
          ...state.neighbors,
          [action.turnId]: { ...existingNeighbors, [chunkId]: action.chunk },
        },
      }
    }
    case 'judge': {
      const existing = state.judgments[action.turnId] ?? {}
      return {
        ...state,
        judgments: {
          ...state.judgments,
          [action.turnId]: { ...existing, [action.chunkId]: action.judgment },
        },
      }
    }
    default:
      return state
  }
}

interface TurnUiContextValue {
  getIncluded: (turnId: number, chunkId: string) => boolean
  /** Count of currently-included chunks for a turn, rail-origin and
   * neighbor-origin combined — what components/ChunkRail.tsx and
   * routes/ChunkDetail.tsx disable their own "Inclure" affordance against
   * once it reaches MAX_INCLUDED_CHUNKS, ahead of the reducer's own no-op
   * guard on 'toggle'/'toggleNeighbor' above (belt-and-braces: the reducer
   * is what actually enforces the cap). */
  getIncludedCount: (turnId: number) => number
  getJudgment: (turnId: number, chunkId: string) => ChunkJudgment | undefined
  getJudgments: (turnId: number) => Record<string, ChunkJudgment>
  /** Every currently-included neighbor-origin chunk for a turn (Sprint 12
   * `feat/chunk-neighbor-expansion`) — what components/ChunkRail.tsx
   * appends after the retrieved-candidates divider, and what
   * state/useTurnController.ts's generate() folds into the /generate
   * request alongside the rail-origin included chunks. */
  getNeighborChunks: (turnId: number) => ChunkNeighborSummary[]
  /** Whether chunkId is one of the turn's originally-retrieved candidates
   * (set at initTurn) — what tells a rail-origin chunk from a
   * neighbor-origin one, e.g. a chunk reached via Screen 4's filmstrip that
   * turns out to already be one of the retrieved 15. Drives both the
   * "Depuis la recherche" / "Voisin — hors des résultats de recherche"
   * origin tag and which toggle (toggleChunk vs toggleNeighborChunk) a
   * focused chunk's Inclure/Exclure button should call. */
  isRetrieved: (turnId: number, chunkId: string) => boolean
  initTurn: (
    turnId: number,
    chunkIds: string[],
    judgments?: Record<string, ChunkJudgment>,
    includedChunkIds?: string[] | null,
    neighborChunks?: ChunkNeighborSummary[],
  ) => void
  toggleChunk: (turnId: number, chunkId: string) => void
  toggleNeighborChunk: (turnId: number, chunk: ChunkNeighborSummary) => void
  setJudgment: (turnId: number, chunkId: string, judgment: ChunkJudgment) => void
}

const TurnUiContext = createContext<TurnUiContextValue | null>(null)

export function TurnUiProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    included: {},
    judgments: {},
    retrievedIds: {},
    neighbors: {},
  })

  const getIncluded = useCallback(
    (turnId: number, chunkId: string) => {
      if (state.neighbors[turnId]?.[chunkId]) return true
      const retrievedIds = state.retrievedIds[turnId]
      // Turn not yet initialized (initTurn hasn't run for it this session)
      // — preserve the old permissive default rather than guessing at
      // origin from an empty set.
      if (retrievedIds === undefined) return state.included[turnId]?.[chunkId] ?? true
      if (retrievedIds.includes(chunkId)) return state.included[turnId]?.[chunkId] ?? true
      // A known, non-retrieved, non-neighbor chunk (e.g. just navigated to
      // via the filmstrip, never included) — never included by default.
      return false
    },
    [state.neighbors, state.retrievedIds, state.included],
  )
  const getIncludedCount = useCallback(
    (turnId: number) => includedCountFor(state, turnId),
    [state],
  )
  const getJudgment = useCallback(
    (turnId: number, chunkId: string) => state.judgments[turnId]?.[chunkId],
    [state.judgments],
  )
  const getJudgments = useCallback(
    (turnId: number) => state.judgments[turnId] ?? {},
    [state.judgments],
  )
  const getNeighborChunks = useCallback(
    (turnId: number) => Object.values(state.neighbors[turnId] ?? {}),
    [state.neighbors],
  )
  const isRetrieved = useCallback(
    (turnId: number, chunkId: string) => state.retrievedIds[turnId]?.includes(chunkId) ?? false,
    [state.retrievedIds],
  )
  const initTurn = useCallback(
    (
      turnId: number,
      chunkIds: string[],
      judgments?: Record<string, ChunkJudgment>,
      includedChunkIds?: string[] | null,
      neighborChunks?: ChunkNeighborSummary[],
    ) => dispatch({ type: 'init', turnId, chunkIds, judgments, includedChunkIds, neighborChunks }),
    [],
  )
  const toggleChunk = useCallback(
    (turnId: number, chunkId: string) => dispatch({ type: 'toggle', turnId, chunkId }),
    [],
  )
  const toggleNeighborChunk = useCallback(
    (turnId: number, chunk: ChunkNeighborSummary) =>
      dispatch({ type: 'toggleNeighbor', turnId, chunk }),
    [],
  )
  const setJudgment = useCallback(
    (turnId: number, chunkId: string, judgment: ChunkJudgment) =>
      dispatch({ type: 'judge', turnId, chunkId, judgment }),
    [],
  )

  return (
    <TurnUiContext.Provider
      value={{
        getIncluded,
        getIncludedCount,
        getJudgment,
        getJudgments,
        getNeighborChunks,
        isRetrieved,
        initTurn,
        toggleChunk,
        toggleNeighborChunk,
        setJudgment,
      }}
    >
      {children}
    </TurnUiContext.Provider>
  )
}

export function useTurnUi(): TurnUiContextValue {
  const ctx = useContext(TurnUiContext)
  if (!ctx) throw new Error('useTurnUi must be used within a TurnUiProvider')
  return ctx
}
