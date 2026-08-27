import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ChunkResult, EvaluateResponse } from '../api/types'
import { toChunkInput } from '../lib/chunkInput'
import { cacheChunks, getCachedChunk } from './chunkCache'
import { useTurnUi } from './turnUi'

export type StepState = 'pending' | 'active' | 'done'
export type EvaluationStatus = 'idle' | 'pending' | 'done' | 'error'

// One row in the turn's generation history: the first, manually-triggered
// /generate plus one entry per subsequent Régénérer click, each keeping its
// own answer, evaluation and reveal state so earlier generations stay
// visible instead of being replaced in place.
export interface GenerationEntry {
  generationId: number | null
  chunkIds: string[]
  state: 'active' | 'done'
  answer: string
  model: string
  evaluation: EvaluateResponse | null
  evaluationStatus: EvaluationStatus
  revealed: boolean
}

export interface TurnControllerOptions {
  /** Set for a turn already persisted — hydrates from GET /turns/{id}. */
  turnId?: number
  /** Set only for a brand-new turn about to be created. */
  pendingQuery?: string
  /** Conversation this new turn belongs to; undefined starts a new conversation. */
  conversationId?: number
  onCreated?: (turnId: number, conversationId: number) => void
}

function patchAt<T>(arr: T[], index: number, patch: Partial<T>): T[] {
  return arr.map((item, i) => (i === index ? { ...item, ...patch } : item))
}

export function useTurnController(options: TurnControllerOptions) {
  const turnUi = useTurnUi()
  const queryClient = useQueryClient()
  const [turnId, setTurnId] = useState<number | null>(options.turnId ?? null)
  const [conversationId, setConversationId] = useState<number | null>(
    options.conversationId ?? null,
  )
  const [query, setQuery] = useState(options.pendingQuery ?? '')
  const [chunks, setChunks] = useState<ChunkResult[]>([])
  const [retrieveState, setRetrieveState] = useState<StepState>('pending')
  const [generations, setGenerations] = useState<GenerationEntry[]>([])
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const hasStarted = useRef(false)

  const runEvaluationAt = useCallback(async (index: number, generationId: number) => {
    setGenerations((prev) => patchAt(prev, index, { evaluationStatus: 'pending' }))
    try {
      const result = await api.evaluate({ generation_id: generationId })
      setGenerations((prev) => patchAt(prev, index, { evaluation: result, evaluationStatus: 'done' }))
    } catch {
      // Evaluation failure (e.g. provider down) shouldn't hide the answer
      // already shown, but the badge must not claim "Vérifié" either —
      // evaluation stays null so retrieval confidence/faithfulness data
      // stays absent from the UI, matching the 'error' status.
      setGenerations((prev) => patchAt(prev, index, { evaluationStatus: 'error' }))
    }
  }, [])

  // /retrieve alone (docs/ROADMAP.md, Sprint 10 turn-lifecycle fix):
  // submitting a query creates its turn — and persists the retrieved chunk
  // set against it — immediately. Generation no longer follows
  // automatically; it only starts once the user clicks "Générer" (see
  // `generate` below). turn_id/conversation_id are known as soon as this
  // resolves, so `onCreated` (the /new -> /c/{id} redirect) fires here too,
  // well before any generation/evaluation network call ever starts —
  // removing the race that used to arise from a route change landing right
  // as the answer/evaluation state was still resolving.
  const runNewTurn = useCallback(
    async (submittedQuery: string) => {
      setQuery(submittedQuery)
      setError(null)
      setRetrieveState('active')
      try {
        const response = await api.retrieve({
          query: submittedQuery,
          conversation_id: options.conversationId,
        })
        cacheChunks(response.chunks)
        setChunks(response.chunks)
        setRetrieveState('done')
        setTurnId(response.turn_id)
        setConversationId(response.conversation_id)
        turnUi.initTurn(
          response.turn_id,
          response.chunks.map((c) => c.chunk_id),
        )
        // The sidebar's conversation list (Sidebar.tsx) doesn't remount on
        // client-side navigation within AppShell, so a freshly created
        // conversation would otherwise never appear there without this.
        void queryClient.invalidateQueries({ queryKey: ['conversations'] })
        void queryClient.invalidateQueries({ queryKey: ['conversation', response.conversation_id] })
        options.onCreated?.(response.turn_id, response.conversation_id)
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
        setRetrieveState('pending')
      }
    },
    [options, queryClient, turnUi],
  )

  // Auto-start a brand-new turn exactly once.
  useEffect(() => {
    if (options.pendingQuery && !hasStarted.current) {
      hasStarted.current = true
      void runNewTurn(options.pendingQuery)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.pendingQuery])

  // Hydrate a persisted turn.
  useEffect(() => {
    if (!options.turnId || options.pendingQuery) return
    let cancelled = false
    const id = options.turnId
    async function hydrate() {
      try {
        const detail = await api.getTurn(id)
        if (cancelled) return
        setConversationId(detail.conversation_id)
        setQuery(detail.query)
        // GET /turns/{id} now re-fetches chunk content live from Qdrant
        // (src/api/main.py:get_turn), so it's as authoritative as the
        // in-session cache — prefer it, falling back to the cache only for
        // a chunk Qdrant no longer has (reindex since this turn was
        // recorded, src/api/models.py's accepted limitation).
        const hydratedChunks = detail.retrieved_chunks.map((rc) =>
          rc.text ? rc : (getCachedChunk(rc.chunk_id) ?? rc),
        )
        cacheChunks(hydratedChunks)
        setChunks(hydratedChunks)
        setRetrieveState('done')
        turnUi.initTurn(
          id,
          detail.retrieved_chunks.map((rc) => rc.chunk_id),
          detail.chunk_judgments,
        )
        const entries: GenerationEntry[] = detail.generations.map((g) => ({
          generationId: g.generation_id,
          chunkIds: g.chunk_ids,
          state: 'done',
          answer: g.answer,
          model: g.model,
          evaluation: g.evaluation,
          evaluationStatus: g.evaluation ? 'done' : 'idle',
          revealed: false,
        }))
        setGenerations(entries)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    }
    void hydrate()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.turnId])

  const reveal = useCallback((index: number) => {
    setGenerations((prev) => patchAt(prev, index, { revealed: true }))
  }, [])

  const evaluate = useCallback(
    (index: number) => {
      const entry = generations[index]
      if (!entry || entry.generationId === null) return
      void runEvaluationAt(index, entry.generationId)
    },
    [generations, runEvaluationAt],
  )

  // The one manual generation trigger (docs/ROADMAP.md, Sprint 10): fires
  // "Générer" for a turn's first generation exactly the same way it fires
  // "Régénérer" for every one after — same request shape, same in-flight
  // guard, same append-a-new-entry behavior. `turn_id` always already
  // exists by the time this can be called (retrieval creates it), so this
  // never creates a turn itself.
  const generate = useCallback(async () => {
    if (turnId === null) return
    const lastEntry = generations.at(-1)
    if (lastEntry && lastEntry.state !== 'done') return
    const newIndex = generations.length
    setIsGenerating(true)
    setError(null)
    try {
      const includedChunks = chunks.filter((c) => turnUi.getIncluded(turnId, c.chunk_id))
      const judgments = turnUi.getJudgments(turnId)
      const chunkIds = includedChunks.map((c) => c.chunk_id)
      setGenerations((prev) => [
        ...prev,
        {
          generationId: null,
          chunkIds,
          state: 'active',
          answer: '',
          model: '',
          evaluation: null,
          evaluationStatus: 'idle',
          revealed: false,
        },
      ])
      const result = await api.generate({
        turn_id: turnId,
        chunks: includedChunks.map(toChunkInput),
        chunk_judgments: judgments,
      })
      setGenerations((prev) =>
        patchAt(prev, newIndex, {
          generationId: result.generation_id,
          answer: result.answer,
          model: result.model_used,
          state: 'done',
        }),
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setGenerations((prev) => prev.slice(0, newIndex))
    } finally {
      setIsGenerating(false)
    }
  }, [chunks, generations, turnId, turnUi])

  const lastGeneration = generations.at(-1)

  return {
    turnId,
    conversationId,
    query,
    chunks,
    retrieveState,
    generations,
    reveal,
    evaluate,
    isGenerating,
    generate,
    // Available once chunks are in and no generation is currently running —
    // covers both the turn's first "Générer" (generations is empty) and
    // every later "Régénérer" (the last generation must have finished).
    canGenerate: retrieveState === 'done' && (!lastGeneration || lastGeneration.state === 'done'),
    error,
  }
}
