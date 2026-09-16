import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { PluggableList } from 'unified'
import { Link } from 'react-router-dom'
import { IconCircleCheck, IconInfoCircle } from '@tabler/icons-react'
import type { EvaluateResponse } from '../api/types'
import type { EvaluationStatus } from '../state/useTurnController'
import { rehypeHighlightClaims } from '../lib/highlightPlugin'
import { rehypeLinkCitations } from '../lib/citationLinkPlugin'
import { CitationFlag } from './CitationFlag'
import { StatusPill } from './StatusPill'

// Generated answers legitimately contain markdown (this project's LLM
// generation, docs/ROADMAP.md Sprint 12) — rendered via react-markdown
// (a maintained parser, not hand-rolled) rather than shown as raw text.
// No custom classes needed for most elements; `mark` and `a` are the two
// tags this component's own rehype plugins introduce
// (lib/highlightPlugin.ts, lib/citationLinkPlugin.ts) — `mark` styled to
// match the previous plain-text `<span>` highlight exactly, `a` styled as a
// small red pill (on user request, `feat/clickable-citations`: a plain
// red/underlined link read as too subtle inline) — same rounded-full
// `--red`/`--red-bg` pill convention as `StatusPill.tsx`/`RelevancePill.tsx`
// elsewhere in this app, reused rather than a third, bespoke pill style —
// and rendered via `Link` (`react-router-dom`) for client-side navigation
// rather than a full page reload; `rehypeLinkCitations` already bakes the
// full in-app path into `href`, so this just forwards it as `to`. The
// surrounding `[`/`]`/separators stay plain text either way (unchanged, see
// lib/citationLinkPlugin.ts) — only the chunk_id token itself is the pill.
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
  a: ({ href, children }: { href?: string; children?: ReactNode }) => (
    <Link
      to={href ?? '#'}
      data-testid="citation-link"
      className="mx-0.5 inline-flex items-center rounded-full px-2 py-0.5 align-middle text-xs font-medium no-underline"
      style={{ background: 'var(--red-bg)', color: 'var(--red)' }}
    >
      {children}
    </Link>
  ),
}

interface AnswerCardProps {
  answer: string
  evaluation: EvaluateResponse | null
  evaluationStatus: EvaluationStatus
  revealed: boolean
  onReveal: () => void
  onEvaluate?: () => void
  // Needed to build each clickable citation's target route
  // (`/c/{conversationId}/turn/{turnId}/chunk/{chunkId}`, the same route
  // Screen 3's "Inspecter" already navigates to, components/ChunkRail.tsx) —
  // null (a not-yet-created turn/conversation) simply disables linkification,
  // same fallback discipline as the confidence-preview/persistence effects
  // elsewhere in this feature (components/ChunkRail.tsx).
  conversationId?: number | null
  turnId?: number | null
}

export function AnswerCard({
  answer,
  evaluation,
  evaluationStatus,
  revealed,
  onReveal,
  onEvaluate,
  conversationId = null,
  turnId = null,
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
  // "Vérifié" (StatusPill) only ever means "the check ran and completed" —
  // it says nothing about the verdict, so a verified-but-still-collapsed
  // card (should_auto_expand false with evaluationStatus 'done') reads as
  // contradictory/buggy without an explanation (user report,
  // fix/answer-verification). should_auto_expand is false iff at least one
  // of these two flags fired (src/generation/guardrail.py) — retrieval
  // confidence used to be a third gate here too, but no longer is
  // (`fix/answer-verification`'s "Dropped: retrieval confidence as an
  // auto-expand gate", same doc): since generation became manual (Sprint
  // 10), the user already sees this same tier pre-generation via
  // ConfidenceGauge/`/confidence-preview` before ever clicking "Générer",
  // so gating the post-generation display on it again no longer adds a
  // check the user hasn't already had the chance to weigh.
  const collapseReason =
    evaluationStatus === 'done'
      ? hasStructuralFlags
        ? 'Un titre ou une date citée semble incorrect(e) : à relire avant de faire confiance à la réponse.'
        : hasFlaggedClaims
          ? 'Un passage surligné n’a pas été retrouvé tel quel dans les sources citées.'
          : null
      : null
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

  // Highlighting runs first so its quote-matching sees the answer's
  // original, unsplit text leaves (lib/highlightMatching.ts's matching rule
  // is unaffected by this feature); linkification then runs over whatever
  // text leaves remain, including inside a `<mark>` the highlight pass just
  // produced — this is what makes a citation bracket sitting inside a
  // flagged quote still become a link nested inside the highlight rather
  // than one transform clobbering the other (explicit regression test,
  // AnswerCard.test.tsx). Citation links are gated on `evaluation` being
  // present at all (no evaluation yet = no confirmed exists-in-input-set
  // result to gate on, so nothing is linked) and on `conversationId`/
  // `turnId` being known (needed to build Screen 4's route).
  const rehypePlugins: PluggableList = []
  if (evaluation) rehypePlugins.push([rehypeHighlightClaims, evaluation.faithfulness.claims])
  if (evaluation && conversationId !== null && turnId !== null) {
    const targetConversationId = conversationId
    const targetTurnId = turnId
    rehypePlugins.push([
      rehypeLinkCitations,
      evaluation.structural.unknown_citations,
      (chunkId: string) => `/c/${targetConversationId}/turn/${targetTurnId}/chunk/${chunkId}`,
    ])
  }

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
          rehypePlugins={rehypePlugins}
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
          className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-8"
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
          {collapseReason && (
            <p
              className="max-w-xs text-center text-xs"
              style={{ color: 'var(--gray-dark)' }}
              data-testid="collapse-reason"
            >
              {collapseReason}
            </p>
          )}
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
