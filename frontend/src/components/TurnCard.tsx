import { useState } from 'react'
import { IconChevronDown, IconChevronUp } from '@tabler/icons-react'
import { computeConsideredSources } from '../lib/retrievalScope'
import type { RetrieveFilterParams } from '../state/retrievalFilter'
import { useTurnController } from '../state/useTurnController'
import { ChunkRail } from './ChunkRail'
import { ConsideredSourceEntry } from './ConsideredSourceEntry'
import { GenerationBlock } from './GenerationBlock'
import { QueryBubble } from './QueryBubble'
import { StepLine } from './StepLine'

interface TurnCardProps {
  turnId?: number
  pendingQuery?: string
  conversationId?: number
  draftId?: string
  filterParams?: RetrieveFilterParams
  onCreated?: (turnId: number, conversationId: number) => void
  onUnknownDraft?: () => void
}

export function TurnCard({
  turnId,
  pendingQuery,
  conversationId,
  draftId,
  filterParams,
  onCreated,
  onUnknownDraft,
}: TurnCardProps) {
  const turn = useTurnController({
    turnId,
    pendingQuery,
    conversationId,
    draftId,
    filterParams,
    onCreated,
    onUnknownDraft,
  })
  const [versionsOpen, setVersionsOpen] = useState(false)
  const consideredSources = computeConsideredSources(turn.filterParams)
  const hasGenerated = turn.generations.length > 0
  // useTurnController keeps `generations` chronological (oldest first,
  // matching GET /turns/{id}'s own `order_by(Generation.id)`,
  // docs/backend_api.md) — generate()'s append-by-index logic depends on
  // that order, so the "most recent first" display (docs/ROADMAP.md,
  // Sprint 12) is a presentation-only reversal here, not a change to that
  // state. Older generations stay reachable rather than disappearing
  // (this project never discards a generation once made, Sprint 7b) behind
  // a chevron toggle — the same collapsed-by-default disclosure
  // interaction as StepLine's own expandable detail above, scaled to a
  // list of whole generations instead of a bullet list.
  const latestIndex = turn.generations.length - 1
  const currentGeneration = latestIndex >= 0 ? turn.generations[latestIndex] : null
  const olderIndices = Array.from({ length: latestIndex }, (_, i) => latestIndex - 1 - i)
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
    // "Régénérer" trigger — its final layout, to the right of the rail,
    // landed on Sprint 12's `feat/chunk-rail-and-citations` (see the flex
    // row below) — starts generation only on explicit click.
    <div
      className="flex flex-col gap-4 rounded-2xl p-6"
      style={{ background: 'var(--paper)', border: '1px solid var(--hairline)' }}
      data-testid="turn-card"
    >
      {turn.query && <QueryBubble query={turn.query} />}

      {turn.retrieveState !== 'pending' && (
        <StepLine label="Recherche des passages pertinents" done={turn.retrieveState === 'done'}>
          {consideredSources && (
            <ul className="flex flex-col gap-2 text-xs" style={{ color: 'var(--ink-3)' }} data-testid="considered-sources">
              {consideredSources.length === 0 && <li>Aucune œuvre ne correspond au filtre.</li>}
              {consideredSources.map((entry) => (
                <ConsideredSourceEntry key={entry.workId} entry={entry} />
              ))}
            </ul>
          )}
        </StepLine>
      )}

      {turn.error && (
        <p className="text-sm" style={{ color: 'var(--red)' }}>
          {turn.error}
        </p>
      )}

      {/* docs/ROADMAP.md, Sprint 12: a single Générer/Régénérer control
          unifying the Sprint 10 manual-generation trigger with the
          regeneration action, positioned to the right of the chunk rail —
          same underlying api.generate() call as before
          (state/useTurnController.ts's `generate`), placement only. The
          rail scrolls horizontally on its own (min-w-0 lets it shrink
          inside the flex row instead of pushing the button off-screen);
          the button sits in a fixed-width column that never scrolls with
          it. */}
      <div className="flex items-start gap-4" data-testid="chunk-rail-row">
        <div className="min-w-0 flex-1">
          <ChunkRail chunks={turn.chunks} turnId={turn.turnId} conversationId={turn.conversationId} />
        </div>

        {turn.canGenerate && (
          <button
            type="button"
            onClick={() => void turn.generate()}
            disabled={turn.isGenerating}
            className="shrink-0 rounded-lg px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            style={{ background: 'var(--red)' }}
          >
            {generateLabel}
          </button>
        )}
      </div>

      {currentGeneration && (
        <GenerationBlock
          key={currentGeneration.generationId ?? `pending-${latestIndex}`}
          entry={currentGeneration}
          isFirst={latestIndex === 0}
          chunks={turn.chunks}
          onReveal={() => turn.reveal(latestIndex)}
          onEvaluate={() => turn.evaluate(latestIndex)}
        />
      )}

      {olderIndices.length > 0 && (
        <div className="flex flex-col gap-4">
          <button
            type="button"
            onClick={() => setVersionsOpen((v) => !v)}
            aria-expanded={versionsOpen}
            data-testid="generation-versions-toggle"
            className="flex items-center gap-1.5 self-start text-xs"
            style={{ color: 'var(--ink-3)' }}
          >
            {versionsOpen ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
            <span>
              {olderIndices.length === 1
                ? '1 version précédente'
                : `${olderIndices.length} versions précédentes`}
            </span>
          </button>

          {versionsOpen && (
            <div
              className="flex flex-col gap-4 pl-3"
              style={{ borderLeft: '1.5px solid var(--hairline)' }}
              data-testid="generation-versions"
            >
              {olderIndices.map((index) => (
                <GenerationBlock
                  key={turn.generations[index].generationId ?? `pending-${index}`}
                  entry={turn.generations[index]}
                  isFirst={index === 0}
                  chunks={turn.chunks}
                  onReveal={() => turn.reveal(index)}
                  onEvaluate={() => turn.evaluate(index)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
