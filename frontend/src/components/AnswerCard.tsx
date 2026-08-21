import { IconCircleCheck, IconInfoCircle } from '@tabler/icons-react'
import type { EvaluateResponse } from '../api/types'
import type { EvaluationStatus } from '../state/useTurnController'
import { annotateAnswer } from '../lib/annotateAnswer'
import { CitationFlag } from './CitationFlag'
import { StatusPill } from './StatusPill'

interface AnswerCardProps {
  answer: string
  evaluation: EvaluateResponse | null
  evaluationStatus: EvaluationStatus
  revealed: boolean
  onReveal: () => void
  onEvaluate?: () => void
}

export function AnswerCard({
  answer,
  evaluation,
  evaluationStatus,
  revealed,
  onReveal,
  onEvaluate,
}: AnswerCardProps) {
  const expanded = revealed || evaluation?.should_auto_expand === true
  const unsupportedClaims = evaluation?.faithfulness.claims.filter((c) => !c.supported) ?? []
  const hasFlaggedClaims = unsupportedClaims.length > 0
  // Every claim the faithfulness judge extracted from the answer was
  // grounded in the cited chunks — the converse of the "highlighted passage"
  // flag below, stated explicitly rather than left implicit in the absence
  // of a warning.
  const fullyEndorsed = !!evaluation && evaluation.faithfulness.claims.length > 0 && !hasFlaggedClaims
  // Reading early via "Lire quand même" must not strand the evaluate control —
  // /evaluate is only ever triggered by this button now, so it has to stay
  // reachable after reveal too, not just in the collapsed overlay.
  const canEvaluate = (evaluationStatus === 'idle' || evaluationStatus === 'error') && onEvaluate
  const evaluateButton = canEvaluate && (
    <button
      type="button"
      onClick={onEvaluate}
      className="rounded-lg border px-4 py-1.5 text-sm font-medium"
      style={{ background: 'var(--paper)', borderColor: 'var(--hairline)', color: 'var(--ink)' }}
    >
      {evaluationStatus === 'error' ? 'Réessayer la vérification' : 'Évaluer'}
    </button>
  )

  return (
    <div
      className="relative overflow-hidden rounded-xl p-4"
      style={{ background: 'var(--paper-2)', border: '0.5px solid var(--hairline)' }}
      data-testid="answer-card"
    >
      {expanded && evaluation && (
        <CitationFlag unknownCitations={evaluation.structural.unknown_citations} />
      )}

      <div
        data-testid="answer-content"
        className="whitespace-pre-wrap text-[15px] leading-relaxed"
        style={{
          color: 'var(--ink)',
          filter: expanded ? 'none' : 'blur(5px)',
        }}
      >
        {evaluation ? annotateAnswer(answer, evaluation.faithfulness.claims) : answer}
      </div>

      {expanded && hasFlaggedClaims && (
        <p className="mt-3 flex items-start gap-1.5 text-xs" style={{ color: 'var(--gray-dark)' }}>
          <IconInfoCircle size={14} className="mt-0.5 shrink-0" />
          <span>Passage surligné : non retrouvé tel quel dans les sources citées</span>
        </p>
      )}

      {expanded && fullyEndorsed && (
        <p className="mt-3 flex items-start gap-1.5 text-xs" style={{ color: 'var(--green)' }}>
          <IconCircleCheck size={14} className="mt-0.5 shrink-0" />
          <span>Réponse intégralement confirmée par les passages cités.</span>
        </p>
      )}

      {expanded && canEvaluate && (
        <div className="mt-3 flex items-center gap-2">
          <StatusPill tone={evaluationStatus === 'error' ? 'failed' : 'pending'} />
          {evaluateButton}
        </div>
      )}

      {!expanded && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center gap-3"
          style={{ background: 'rgba(250,246,238,0.4)' }}
        >
          <StatusPill
            tone={
              evaluationStatus === 'pending'
                ? 'verifying'
                : evaluationStatus === 'done'
                  ? 'verified'
                  : evaluationStatus === 'error'
                    ? 'failed'
                    : 'pending'
            }
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onReveal}
              className="rounded-lg border px-4 py-1.5 text-sm font-medium"
              style={{ background: 'var(--paper)', borderColor: 'var(--hairline)', color: 'var(--ink)' }}
            >
              Lire quand même
            </button>
            {evaluateButton}
          </div>
        </div>
      )}
    </div>
  )
}
