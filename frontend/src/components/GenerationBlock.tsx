import type { ChunkResult } from '../api/types'
import type { GenerationEntry } from '../state/useTurnController'
import { computeIncludedChunks } from '../lib/generationChunks'
import { AnswerCard } from './AnswerCard'
import { StepLine } from './StepLine'

interface GenerationBlockProps {
  entry: GenerationEntry
  isFirst: boolean
  /** The turn's retrieved chunks (state/useTurnController.ts) — used to
   * resolve `entry.chunkIds` to a citation (lib/citation.ts) for the
   * "Génération..." step's expandable included-chunks list below. */
  chunks: ChunkResult[]
  onReveal: () => void
  onEvaluate: () => void
}

// One generation and everything chronologically tied to it: the
// "Génération…" step, the answer, and its own verification status. The
// Générer/Régénérer trigger itself lives one level up (TurnCard.tsx) — a
// single control for the whole turn, not per-generation — since it must
// also be shown before any generation exists yet (docs/ROADMAP.md, Sprint
// 10 manual-generation reversal). Regenerating adds another one of these
// rather than replacing this one, so earlier answers stay reachable
// (docs/ROADMAP.md, Sprint 12 — TurnCard.tsx shows the most recent one
// primary and the rest behind a "versions" disclosure).
export function GenerationBlock({ entry, isFirst, chunks, onReveal, onEvaluate }: GenerationBlockProps) {
  const generateLabel = isFirst ? 'Génération de la réponse' : "Génération d'une nouvelle réponse"
  const verifyLabel =
    entry.evaluationStatus === 'done'
      ? 'Vérification terminée'
      : entry.evaluationStatus === 'error'
        ? 'Vérification indisponible'
        : 'Vérification en cours'

  // Known as soon as "Générer"/"Régénérer" is clicked (state/
  // useTurnController.ts's generate() sets chunkIds on the entry before the
  // /generate request even resolves), so the chevron is offered right away,
  // same "available before the step finishes" rule as the retrieval step's
  // own expandable detail (components/TurnCard.tsx).
  const includedChunks = computeIncludedChunks(entry.chunkIds, chunks)
  const includedChunksList =
    includedChunks.length === 0 ? undefined : (
      <ul className="flex flex-col gap-1 text-xs" style={{ color: 'var(--ink-3)' }} data-testid="included-chunks">
        {includedChunks.map((c) => (
          <li key={c.chunkId}>
            <span data-testid="chunk-citation">{c.citation}</span>
          </li>
        ))}
      </ul>
    )

  return (
    <div className="flex flex-col gap-4">
      <StepLine label={generateLabel} done={entry.state === 'done'} expandLabel="les passages inclus dans la génération">
        {includedChunksList}
      </StepLine>

      {entry.state === 'done' && (
        <>
          <AnswerCard
            answer={entry.answer}
            evaluation={entry.evaluation}
            evaluationStatus={entry.evaluationStatus}
            revealed={entry.revealed}
            onReveal={onReveal}
            onEvaluate={onEvaluate}
          />

          {entry.evaluationStatus !== 'idle' && (
            <StepLine
              label={verifyLabel}
              done={entry.evaluationStatus === 'done' || entry.evaluationStatus === 'error'}
              failed={entry.evaluationStatus === 'error'}
            />
          )}
        </>
      )}
    </div>
  )
}
