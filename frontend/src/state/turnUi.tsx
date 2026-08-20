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
      for (const id of action.chunkIds) {
        if (!(id in nextIncluded)) nextIncluded[id] = true
      }
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
      value={{ getIncluded, getJudgment, getJudgments, initTurn, toggleChunk, setJudgment }}
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
