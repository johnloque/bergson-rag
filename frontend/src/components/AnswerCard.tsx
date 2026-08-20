import { IconInfoCircle } from '@tabler/icons-react'
import type { EvaluateResponse } from '../api/types'
import type { EvaluationStatus } from '../state/useTurnController'
import { annotateAnswer } from '../lib/annotateAnswer'
import { CitationFlag } from './CitationFlag'
import { ConfidenceGauge } from './ConfidenceGauge'
import { StatusPill } from './StatusPill'

interface AnswerCardProps {
  answer: string
  evaluation: EvaluateResponse | null
  evaluationStatus: EvaluationStatus
  revealed: boolean
  onReveal: () => void
}

export function AnswerCard({ answer, evaluation, evaluationStatus, revealed, onReveal }: AnswerCardProps) {
  const expanded = revealed || evaluation?.should_auto_expand === true
  const unsupportedClaims = evaluation?.faithfulness.claims.filter((c) => !c.supported) ?? []
  const hasFlaggedClaims = unsupportedClaims.length > 0

  return (
    <div
      className="relative overflow-hidden rounded-xl p-4"
      style={{ background: 'var(--paper-2)' }}
      data-testid="answer-card"
    >
      {evaluation?.retrieval_confidence_tier && expanded && (
        <div className="mb-3">
          <ConfidenceGauge tier={evaluation.retrieval_confidence_tier} />
        </div>
      )}

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
                  : 'pending'
            }
          />
          <button
            type="button"
            onClick={onReveal}
            className="rounded-lg border px-4 py-1.5 text-sm font-medium"
            style={{ background: 'var(--paper)', borderColor: 'var(--hairline)', color: 'var(--ink)' }}
          >
            Lire quand même
          </button>
        </div>
      )}
    </div>
  )
}
