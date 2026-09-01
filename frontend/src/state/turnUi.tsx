import { createContext, useCallback, useContext, useReducer, type ReactNode } from 'react'
import type { ChunkJudgment } from '../api/types'

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
}

type Action =
  | { type: 'init'; turnId: number; chunkIds: string[]; judgments?: Record<string, ChunkJudgment> }
  | { type: 'toggle'; turnId: number; chunkId: string }
  | { type: 'judge'; turnId: number; chunkId: string; judgment: ChunkJudgment }

function reducer(state: TurnUiState, action: Action): TurnUiState {
  switch (action.type) {
    case 'init': {
      const existing = state.included[action.turnId] ?? {}
      const nextIncluded = { ...existing }
      // Top DEFAULT_INCLUDED_COUNT (by rank — action.chunkIds is always in
      // the turn's reranked order, state/useTurnController.ts) default to
      // included; the rest default to explicitly excluded, not to the
      // `getIncluded` fallback below — every chunk from a real /retrieve or
      // GET /turns/{id} response gets a concrete entry here, so that
      // fallback only ever matters for a chunk this reducer has never seen.
      action.chunkIds.forEach((id, index) => {
        if (!(id in nextIncluded)) nextIncluded[id] = index < DEFAULT_INCLUDED_COUNT
      })
      const nextJudgments = action.judgments
        ? { ...action.judgments, ...state.judgments[action.turnId] }
        : state.judgments[action.turnId]
      return {
        included: { ...state.included, [action.turnId]: nextIncluded },
        judgments: { ...state.judgments, [action.turnId]: nextJudgments ?? {} },
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
        const includedCount = Object.values(existing).filter(Boolean).length
        if (includedCount >= MAX_INCLUDED_CHUNKS) return state
      }
      return {
        ...state,
        included: {
          ...state.included,
          [action.turnId]: { ...existing, [action.chunkId]: !current },
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
  /** Count of currently-included chunks for a turn — what
   * components/ChunkRail.tsx and routes/ChunkDetail.tsx disable their own
   * "Inclure" affordance against once it reaches MAX_INCLUDED_CHUNKS, ahead
   * of the reducer's own no-op guard on 'toggle' above (belt-and-braces:
   * the reducer is what actually enforces the cap). */
  getIncludedCount: (turnId: number) => number
  getJudgment: (turnId: number, chunkId: string) => ChunkJudgment | undefined
  getJudgments: (turnId: number) => Record<string, ChunkJudgment>
  initTurn: (turnId: number, chunkIds: string[], judgments?: Record<string, ChunkJudgment>) => void
  toggleChunk: (turnId: number, chunkId: string) => void
  setJudgment: (turnId: number, chunkId: string, judgment: ChunkJudgment) => void
}

const TurnUiContext = createContext<TurnUiContextValue | null>(null)

export function TurnUiProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, { included: {}, judgments: {} })

  const getIncluded = useCallback(
    (turnId: number, chunkId: string) => state.included[turnId]?.[chunkId] ?? true,
    [state.included],
  )
  const getIncludedCount = useCallback(
    (turnId: number) => Object.values(state.included[turnId] ?? {}).filter(Boolean).length,
    [state.included],
  )
  const getJudgment = useCallback(
    (turnId: number, chunkId: string) => state.judgments[turnId]?.[chunkId],
    [state.judgments],
  )
  const getJudgments = useCallback(
    (turnId: number) => state.judgments[turnId] ?? {},
    [state.judgments],
  )
  const initTurn = useCallback(
    (turnId: number, chunkIds: string[], judgments?: Record<string, ChunkJudgment>) =>
      dispatch({ type: 'init', turnId, chunkIds, judgments }),
    [],
  )
  const toggleChunk = useCallback(
    (turnId: number, chunkId: string) => dispatch({ type: 'toggle', turnId, chunkId }),
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
        initTurn,
        toggleChunk,
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
