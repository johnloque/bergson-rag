import { useSyncExternalStore } from 'react'

export interface InFlightEntry<T> {
  status: 'pending' | 'error'
  error?: string
  promise: Promise<T>
}

// A request that survives the component that started it. Plain useState
// (retrieveState, isGenerating, ...) resets to its initial value whenever
// its owning component unmounts — which happens on ordinary in-app
// navigation (leaving a conversation, clicking "Nouvelle conversation"),
// not just a page reload. Returning to that same request afterwards then
// shows no sign it's still running, inviting a second click that fires a
// real duplicate call. Keying requests here instead, module-level, lets any
// later mount for the same `key` attach to the one already in flight
// instead of starting another.
export class InFlightRegistry<T> {
  private entries = new Map<string, InFlightEntry<T>>()
  private listeners = new Set<() => void>()

  private emit() {
    for (const listener of this.listeners) listener()
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  get = (key: string): InFlightEntry<T> | undefined => this.entries.get(key)

  /** Starts `run()` under `key`, or returns the promise already running for
   * it — never calls `run()` a second time while the first is pending. */
  start(key: string, run: () => Promise<T>): Promise<T> {
    const existing = this.entries.get(key)
    if (existing) return existing.promise

    const promise = run().then(
      (result) => {
        this.entries.delete(key)
        this.emit()
        return result
      },
      (e: unknown) => {
        this.entries.set(key, {
          status: 'error',
          error: e instanceof Error ? e.message : String(e),
          promise,
        })
        this.emit()
        throw e
      },
    )
    this.entries.set(key, { status: 'pending', promise })
    this.emit()
    return promise
  }
}

export function useInFlightEntry<T>(
  registry: InFlightRegistry<T>,
  key: string | null,
): InFlightEntry<T> | undefined {
  return useSyncExternalStore(registry.subscribe, () => (key === null ? undefined : registry.get(key)))
}
