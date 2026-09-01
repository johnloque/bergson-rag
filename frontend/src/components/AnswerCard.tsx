import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { IconCircleCheck, IconInfoCircle } from '@tabler/icons-react'
import type { EvaluateResponse } from '../api/types'
import type { EvaluationStatus } from '../state/useTurnController'
import { rehypeHighlightClaims } from '../lib/highlightPlugin'
import { CitationFlag } from './CitationFlag'
import { StatusPill } from './StatusPill'

// Generated answers legitimately contain markdown (this project's LLM
// generation, docs/ROADMAP.md Sprint 12) — rendered via react-markdown
// (a maintained parser, not hand-rolled) rather than shown as raw text.
// No custom classes needed for most elements; `mark` is the one tag this
// component's own highlight plugin introduces (lib/highlightPlugin.ts),
// styled here to match the previous plain-text `<span>` highlight exactly.
const markdownComponents = {
  p: ({ children }: { children?: ReactNode }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="mb-2 list-disc pl-5 last:mb-0">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="mb-2 list-decimal pl-5 last:mb-0">{children}</ol>
  ),
  li: ({ children }: { children?: ReactNode }) => <li className="mb-0.5">{children}</li>,
  mark: ({ children }: { children?: ReactNode }) => (
    <mark style={{ background: 'var(--gray-dark-bg)', borderBottom: '1.5px solid var(--gray-dark)' }}>
      {children}
    </mark>
  ),
}

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
  // Layer 1's own positive, specific claims (a fabricated title, or a real
  // title paired with the wrong year) — unlike unknown_citations, both
  // already gate should_auto_expand (src/generation/guardrail.py) and must
  // also suppress the "fully endorsed" statement below: Layer 2 (the
  // faithfulness judge) can score an answer 1.0 while missing exactly this
  // failure mode (the real Q002 case that motivated check_title_fabrication
  // in the first place, docs/anti_hallucination_guardrails.md), so "fully
  // confirmed by the cited passages" must not be claimed on Layer 2's
  // verdict alone.
  const hasStructuralFlags =
    !!evaluation &&
    (evaluation.structural.fabricated_titles.length > 0 ||
      evaluation.structural.title_year_mismatches.length > 0)
  // Every claim the faithfulness judge extracted from the answer was
  // grounded in the cited chunks — the converse of the "highlighted passage"
  // flag below, stated explicitly rather than left implicit in the absence
  // of a warning.
  const fullyEndorsed =
    !!evaluation &&
    evaluation.faithfulness.claims.length > 0 &&
    !hasFlaggedClaims &&
    !hasStructuralFlags
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
        <CitationFlag
          unknownCitations={evaluation.structural.unknown_citations}
          fabricatedTitles={evaluation.structural.fabricated_titles}
          titleYearMismatches={evaluation.structural.title_year_mismatches}
        />
      )}

      <div
        data-testid="answer-content"
        className="text-[15px] leading-relaxed"
        style={{
          color: 'var(--ink)',
          filter: expanded ? 'none' : 'blur(5px)',
        }}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={evaluation ? [[rehypeHighlightClaims, evaluation.faithfulness.claims]] : []}
          components={markdownComponents}
        >
          {answer}
        </ReactMarkdown>
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
