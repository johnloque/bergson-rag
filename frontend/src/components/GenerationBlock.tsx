import type { GenerationEntry } from '../state/useTurnController'
import { AnswerCard } from './AnswerCard'
import { StepLine } from './StepLine'

interface GenerationBlockProps {
  entry: GenerationEntry
  isFirst: boolean
  onReveal: () => void
  onEvaluate: () => void
}

// One generation and everything chronologically tied to it: the
// "Génération…" step, the answer, and its own verification status. The
// Générer/Régénérer trigger itself lives one level up (TurnCard.tsx) — a
// single control for the whole turn, not per-generation — since it must
// also be shown before any generation exists yet (docs/ROADMAP.md, Sprint
// 10 manual-generation reversal). Regenerating adds another one of these
// below rather than replacing this one, so earlier answers stay visible
// (docs/ROADMAP.md, Sprint 8, Screen 3).
export function GenerationBlock({ entry, isFirst, onReveal, onEvaluate }: GenerationBlockProps) {
  const generateLabel = isFirst
    ? 'Génération de la réponse'
    : `Génération d'une nouvelle réponse (${entry.chunkIds.join(', ')})`
  const verifyLabel =
    entry.evaluationStatus === 'done'
      ? 'Vérification terminée'
      : entry.evaluationStatus === 'error'
        ? 'Vérification indisponible'
        : 'Vérification en cours'

  return (
    <div className="flex flex-col gap-4">
      <StepLine label={generateLabel} done={entry.state === 'done'} />

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
