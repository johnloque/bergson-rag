import type { GenerationEntry } from '../state/useTurnController'
import { AnswerCard } from './AnswerCard'
import { StepLine } from './StepLine'

interface GenerationBlockProps {
  entry: GenerationEntry
  isFirst: boolean
  isLast: boolean
  canRegenerate: boolean
  isRegenerating: boolean
  onReveal: () => void
  onEvaluate: () => void
  onRegenerate: () => void
}

// One generation and everything chronologically tied to it: the
// "Génération…" step, the answer, its own verification status, and (only
// for the most recent generation) the Régénérer button. Regenerating adds
// another one of these below rather than replacing this one, so earlier
// answers stay visible (docs/ROADMAP.md, Sprint 8, Screen 3).
export function GenerationBlock({
  entry,
  isFirst,
  isLast,
  canRegenerate,
  isRegenerating,
  onReveal,
  onEvaluate,
  onRegenerate,
}: GenerationBlockProps) {
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

          {isLast && canRegenerate && (
            <div>
              <button
                type="button"
                onClick={onRegenerate}
                disabled={isRegenerating}
                className="rounded-lg border px-4 py-1.5 text-sm font-medium disabled:opacity-50"
                style={{ background: 'var(--paper)', borderColor: 'var(--hairline)', color: 'var(--ink)' }}
              >
                {isRegenerating ? 'Régénération…' : 'Régénérer'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
