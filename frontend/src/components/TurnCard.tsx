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

  return (
    <div
      className="flex flex-col gap-4 rounded-xl p-5"
      style={{ border: '0.5px solid var(--hairline)', background: 'var(--paper)' }}
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

      {turn.generations.map((entry, index) => (
        <GenerationBlock
          key={entry.generationId ?? `pending-${index}`}
          entry={entry}
          isFirst={index === 0}
          isLast={index === turn.generations.length - 1}
          canRegenerate={turn.canRegenerate}
          isRegenerating={turn.isRegenerating}
          onReveal={() => turn.reveal(index)}
          onEvaluate={() => turn.evaluate(index)}
          onRegenerate={() => void turn.regenerate()}
        />
      ))}
    </div>
  )
}
