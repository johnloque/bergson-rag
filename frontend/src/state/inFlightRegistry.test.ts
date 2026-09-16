import { describe, expect, it } from 'vitest'
import { InFlightRegistry } from './inFlightRegistry'

describe('InFlightRegistry', () => {
  it('dedupes a second start() under the same key while the first is pending', async () => {
    let runCount = 0
    const registry = new InFlightRegistry<string>()
    const run = () => {
      runCount += 1
      return Promise.resolve('done')
    }

    const [a, b] = await Promise.all([registry.start('k', run), registry.start('k', run)])
    expect(a).toBe('done')
    expect(b).toBe('done')
    expect(runCount).toBe(1)
  })

  // fix/answer-verification: state/pendingEvaluations.ts reuses this class
  // for /evaluate's manual "Réessayer la vérification" retry button — a
  // failed call must not permanently poison the key, or every retry after
  // the first failure would silently replay the same stale rejection
  // instead of actually calling /evaluate again.
  it('clears the entry on failure so the next start() for the same key genuinely retries', async () => {
    let runCount = 0
    const registry = new InFlightRegistry<string>()

    await expect(
      registry.start('k', () => {
        runCount += 1
        return Promise.reject(new Error('boom'))
      }),
    ).rejects.toThrow('boom')

    expect(registry.get('k')).toBeUndefined()

    const result = await registry.start('k', () => {
      runCount += 1
      return Promise.resolve('recovered')
    })
    expect(result).toBe('recovered')
    expect(runCount).toBe(2)
  })
})
