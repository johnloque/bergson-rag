import { useTurnController } from '../state/useTurnController'
import { ChunkRail } from './ChunkRail'
import { GenerationBlock } from './GenerationBlock'
import { QueryBubble } from './QueryBubble'
import { StepLine } from './StepLine'

interface TurnCardProps {
  turnId?: number
  pendingQuery?: string
  conversationId?: number
  onCreated?: (turnId: number, conversationId: number) => void
}

export function TurnCard({ turnId, pendingQuery, conversationId, onCreated }: TurnCardProps) {
  const turn = useTurnController({ turnId, pendingQuery, conversationId, onCreated })
  const hasGenerated = turn.generations.length > 0
  const generateLabel = hasGenerated
    ? turn.isGenerating
      ? 'Régénération…'
      : 'Régénérer'
    : turn.isGenerating
      ? 'Génération…'
      : 'Générer'

  return (
    // Each turn renders as one visually self-contained unit (query,
    // processing steps, chunk rail, answer) — a bordered card, not a
    // continuous chat bubble — because there is no cross-turn context: every
    // query triggers its own independent retrieve+generate cycle
    // (docs/ROADMAP.md, Sprint 8 addendum). Generation no longer follows
    // retrieval automatically (docs/ROADMAP.md, Sprint 10): the chunk rail
    // renders as soon as retrieval completes, and a single "Générer"/
    // "Régénérer" trigger — minimal placement for now, Sprint 12 owns the
    // final layout — starts generation only on explicit click.
    <div
      className="flex flex-col gap-4 rounded-2xl p-6"
      style={{ background: 'var(--paper)', border: '1px solid var(--hairline)' }}
      data-testid="turn-card"
    >
      {turn.query && <QueryBubble query={turn.query} />}

      {turn.retrieveState !== 'pending' && (
        <StepLine label="Recherche des passages pertinents" done={turn.retrieveState === 'done'} />
      )}

      {turn.error && (
        <p className="text-sm" style={{ color: 'var(--red)' }}>
          {turn.error}
        </p>
      )}

      <ChunkRail chunks={turn.chunks} turnId={turn.turnId} conversationId={turn.conversationId} />

      {turn.canGenerate && (
        <div>
          <button
            type="button"
            onClick={() => void turn.generate()}
            disabled={turn.isGenerating}
            className="rounded-lg px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            style={{ background: 'var(--red)' }}
          >
            {generateLabel}
          </button>
        </div>
      )}

      {turn.generations.map((entry, index) => (
        <GenerationBlock
          key={entry.generationId ?? `pending-${index}`}
          entry={entry}
          isFirst={index === 0}
          onReveal={() => turn.reveal(index)}
          onEvaluate={() => turn.evaluate(index)}
        />
      ))}
    </div>
  )
}
