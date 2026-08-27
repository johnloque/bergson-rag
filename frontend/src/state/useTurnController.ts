import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ChunkResult, EvaluateResponse } from '../api/types'
import { toChunkInput } from '../lib/chunkInput'
import { cacheChunks, getCachedChunk } from './chunkCache'
import { getPendingConversation, startOrAttachPendingConversation } from './pendingConversations'
import { pendingGenerations } from './pendingGenerations'
import { useTurnUi } from './turnUi'

export type StepState = 'pending' | 'active' | 'done'
export type EvaluationStatus = 'idle' | 'pending' | 'done' | 'error'

// How long the hydrate effect below will keep polling GET /turns/{id} for a
// turn whose retrieved_chunks come back empty before giving up and showing
// it anyway (see the hydrate effect's own comment for why empty means "not
// finished", not "nothing found"). 30 * 2s = 60s, comfortably above this
// deployment's observed worst-case /retrieve latency.
const HYDRATE_MAX_RETRIES = 30
const HYDRATE_RETRY_DELAY_MS = 2000

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
  /** Set only for a brand-new conversation's first turn — the id in the
   * `/new/:draftId` URL. Routes the initial /retrieve call through
   * state/pendingConversations.ts instead of calling it directly, so
   * revisiting the same `/new/:draftId` (sidebar click, browser back)
   * reattaches to it instead of firing a second one. */
  draftId?: string
  onCreated?: (turnId: number, conversationId: number) => void
  /** Called when `draftId` doesn't resolve to anything startable — no
   * pending/errored entry for it and no query to start fresh with either
   * (e.g. a stale /new/:draftId visit after that submission already
   * resolved and was dropped from the pending list). */
  onUnknownDraft?: () => void
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
  // as the answer/evaluation state was still resolving. This path is for a
  // follow-up turn in an already-existing conversation only — a brand-new
  // conversation's first turn always goes through `runDraftTurn` below.
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
        void queryClient.invalidateQueries({ queryKey: ['conversation', response.conversation_id] })
        options.onCreated?.(response.turn_id, response.conversation_id)
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
        setRetrieveState('pending')
      }
    },
    [options, queryClient, turnUi],
  )

  // A brand-new conversation's first turn: the /retrieve call itself is
  // owned by state/pendingConversations.ts, keyed by `draftId` (the
  // `/new/:draftId` URL), not by this component — see that module's
  // docstring for why. This function just attaches to it and mirrors the
  // result into local state exactly like `runNewTurn` above.
  const runDraftTurn = useCallback(
    async (draftId: string, submittedQuery: string) => {
      setQuery(submittedQuery)
      setError(null)
      setRetrieveState('active')
      try {
        const result = await startOrAttachPendingConversation(queryClient, draftId, submittedQuery)
        cacheChunks(result.chunks)
        setChunks(result.chunks)
        setRetrieveState('done')
        setTurnId(result.turnId)
        setConversationId(result.conversationId)
        turnUi.initTurn(
          result.turnId,
          result.chunks.map((c) => c.chunk_id),
        )
        void queryClient.invalidateQueries({ queryKey: ['conversation', result.conversationId] })
        options.onCreated?.(result.turnId, result.conversationId)
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
        setRetrieveState('pending')
      }
    },
    [options, queryClient, turnUi],
  )

  // Auto-start a brand-new turn exactly once — via the draft-attaching path
  // when `draftId` is set, directly otherwise (an existing conversation's
  // follow-up turn, which needs no cross-navigation resumability since its
  // conversation already has a stable, always-reachable sidebar entry).
  useEffect(() => {
    if (hasStarted.current) return
    if (options.draftId) {
      hasStarted.current = true
      const draftId = options.draftId
      const existing = getPendingConversation(draftId)
      const initialQuery = existing?.query ?? options.pendingQuery
      if (!initialQuery) {
        options.onUnknownDraft?.()
        return
      }
      void runDraftTurn(draftId, initialQuery)
    } else if (options.pendingQuery) {
      hasStarted.current = true
      void runNewTurn(options.pendingQuery)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.pendingQuery, options.draftId])

  // Hydrate a persisted turn.
  useEffect(() => {
    if (!options.turnId || options.pendingQuery) return
    let cancelled = false
    const id = options.turnId
    async function hydrate(attempt = 0) {
      try {
        const detail = await api.getTurn(id)
        if (cancelled) return

        // persistence.create_turn (src/api/persistence.py) commits the turn
        // well before /retrieve finishes hybrid search + reranking and
        // saves its retrieved_chunks (src/api/main.py) — so a turn hydrated
        // right in that window (this page reached before the client that
        // started it ever saw /retrieve resolve: a hard refresh, or the
        // sidebar's real row appearing early via React Query's default
        // refetch-on-window-focus while the conversation's first retrieve
        // is still running) can legitimately come back with none yet.
        // Reporting that as "done" was the actual bug here: it showed a
        // checkmark plus an empty chunk rail and a generate button as if
        // retrieval had genuinely found nothing, when it just hadn't
        // finished. Poll briefly instead — hybrid search over a real corpus
        // always returns top_k candidates once it runs, so an empty result
        // means "not finished", never "nothing found".
        if (detail.retrieved_chunks.length === 0 && attempt < HYDRATE_MAX_RETRIES) {
          setRetrieveState('active')
          await new Promise((resolve) => setTimeout(resolve, HYDRATE_RETRY_DELAY_MS))
          if (!cancelled) await hydrate(attempt + 1)
          return
        }

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
        const persistedEntries: GenerationEntry[] = detail.generations.map((g) => ({
          generationId: g.generation_id,
          chunkIds: g.chunk_ids,
          state: 'done',
          answer: g.answer,
          model: g.model,
          evaluation: g.evaluation,
          evaluationStatus: g.evaluation ? 'done' : 'idle',
          revealed: false,
        }))
        setGenerations(persistedEntries)

        // A "Générer"/"Régénérer" click made before this mount (e.g. the
        // user navigated away right after clicking, then back) may still be
        // running server-side with no persisted row to show for it yet —
        // resume its spinner and attach to the same call instead of leaving
        // the UI looking idle (which is what invited a second click; see
        // pendingGenerations.ts).
        const inFlight = pendingGenerations.get(String(id))
        if (inFlight) {
          const resumeIndex = persistedEntries.length
          setIsGenerating(true)
          setGenerations((prev) => [
            ...prev,
            {
              generationId: null,
              chunkIds: [],
              state: 'active',
              answer: '',
              model: '',
              evaluation: null,
              evaluationStatus: 'idle',
              revealed: false,
            },
          ])
          inFlight.promise.then(
            (result) => {
              if (cancelled) return
              setGenerations((prev) =>
                patchAt(prev, resumeIndex, {
                  generationId: result.generationId,
                  answer: result.answer,
                  model: result.model,
                  state: 'done',
                }),
              )
              setIsGenerating(false)
            },
            () => {
              if (cancelled) return
              setGenerations((prev) => prev.slice(0, resumeIndex))
              setIsGenerating(false)
            },
          )
        }
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
      // Registered under the turn id (pendingGenerations.ts) so that if this
      // component unmounts before /generate resolves — the user navigated
      // away — a later remount of this same turn's card (the hydrate effect
      // above) can find it still running and reattach, instead of the UI
      // just looking idle again and inviting a second "Générer" click.
      const result = await pendingGenerations.start(String(turnId), () =>
        api.generate({
          turn_id: turnId,
          chunks: includedChunks.map(toChunkInput),
          chunk_judgments: judgments,
        }).then((r) => ({ generationId: r.generation_id, answer: r.answer, model: r.model_used })),
      )
      setGenerations((prev) =>
        patchAt(prev, newIndex, {
          generationId: result.generationId,
          answer: result.answer,
          model: result.model,
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
