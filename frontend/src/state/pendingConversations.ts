import { useSyncExternalStore } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ChunkResult } from '../api/types'
import type { RetrieveFilterParams } from './retrievalFilter'

// A brand-new conversation's first /retrieve call, keyed by the id in the
// `/new/:draftId` URL (App.tsx) rather than by conversation_id, which
// doesn't exist yet. This is what lets the sidebar's pending placeholder
// (Sidebar.tsx) be a real, clickable link: visiting `/new/:draftId` again —
// from the sidebar, or the browser back button — reattaches to the one
// /retrieve call already running under that id instead of firing a second
// one, wherever the user navigated to in between (state/inFlightRegistry.ts
// explains why component-local state alone can't do this).
export interface PendingConversationResult {
  turnId: number
  conversationId: number
  chunks: ChunkResult[]
}

interface Entry {
  query: string
  filterParams: RetrieveFilterParams
  status: 'retrieving' | 'error'
  error?: string
  promise: Promise<PendingConversationResult>
}

export interface PendingConversationSummary {
  draftId: string
  query: string
}

const entries = new Map<string, Entry>()
const listeners = new Set<() => void>()
// useSyncExternalStore needs a stable reference when nothing relevant
// changed — rebuilt only in emit(), not on every getSnapshot() call (a
// fresh array every render would look like a perpetual change and loop).
let listSnapshot: PendingConversationSummary[] = []

function rebuildListSnapshot() {
  listSnapshot = Array.from(entries.entries())
    .filter(([, entry]) => entry.status === 'retrieving')
    .map(([draftId, entry]) => ({ draftId, query: entry.query }))
}

function emit() {
  rebuildListSnapshot()
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function getListSnapshot() {
  return listSnapshot
}

export function getPendingConversation(draftId: string): Entry | undefined {
  return entries.get(draftId)
}

/** Starts the /retrieve call for `draftId`'s first submission, or — if one
 * is already running or already failed under that id — returns its
 * existing promise instead of calling /retrieve again. `filterParams` is
 * only consulted on that first call (routes/Conversation.tsx captures it at
 * submit time); a later attach to an already-running/failed entry ignores
 * whatever is passed here and uses what the entry started with. */
export function startOrAttachPendingConversation(
  queryClient: QueryClient,
  draftId: string,
  query: string,
  filterParams: RetrieveFilterParams = {},
): Promise<PendingConversationResult> {
  const existing = entries.get(draftId)
  if (existing) return existing.promise

  const promise: Promise<PendingConversationResult> = api
    .retrieve({ query, conversation_id: undefined, ...filterParams })
    .then(async (response) => {
      const result: PendingConversationResult = {
        turnId: response.turn_id,
        conversationId: response.conversation_id,
        chunks: response.chunks,
      }
      // Awaited (not fire-and-forget) so the real sidebar row is already in
      // the cache by the time this draft is dropped from the pending list
      // below, instead of the sidebar briefly showing neither.
      await queryClient.invalidateQueries({ queryKey: ['conversations'] })
      entries.delete(draftId)
      emit()
      return result
    })
    .catch((e: unknown) => {
      entries.set(draftId, {
        query,
        filterParams,
        status: 'error',
        error: e instanceof Error ? e.message : String(e),
        promise,
      })
      emit()
      throw e
    })

  entries.set(draftId, { query, filterParams, status: 'retrieving', promise })
  emit()
  return promise
}

export function usePendingConversationsList(): PendingConversationSummary[] {
  return useSyncExternalStore(subscribe, getListSnapshot, getListSnapshot)
}
