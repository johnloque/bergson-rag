import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ComponentPropsWithoutRef,
  type CSSProperties,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
} from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { PluggableList } from 'unified'
import { Link } from 'react-router-dom'
import { IconCircleCheck, IconInfoCircle } from '@tabler/icons-react'
import type { EvaluateResponse } from '../api/types'
import type { EvaluationStatus } from '../state/useTurnController'
import { rehypeSegments } from '../lib/segmentPlugin'
import { groupClaimsBySegment, segmentStatus, type SegmentStatus } from '../lib/segmentVerdicts'
import { rehypeLinkCitations } from '../lib/citationLinkPlugin'
import { CitationFlag } from './CitationFlag'
import { SegmentPopover } from './SegmentPopover'
import { StatusPill } from './StatusPill'

// Generated answers legitimately contain markdown (this project's LLM
// generation, docs/ROADMAP.md Sprint 12) — rendered via react-markdown
// (a maintained parser, not hand-rolled) rather than shown as raw text.
// No custom classes needed for most elements; `span` and `a` are the two
// tags this component's own rehype plugins introduce
// (lib/segmentPlugin.ts, lib/citationLinkPlugin.ts) — a `span` carrying
// `data-segment-id` is a checked answer sentence, rendered by `SegmentSpan`
// below; `a` is styled as a small red pill (on user request, `feat/clickable-citations`: a plain
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
  // A `span` carrying `data-segment-id` comes from lib/segmentPlugin.ts.
  span: ({ node: _node, children, ...props }: SpanProps) => {
    const data = props as Record<string, unknown>
    const id = data['data-segment-id']
    const status = data['data-segment-status'] as SegmentStatus | undefined
    if (id === undefined || !status) return <span {...props}>{children}</span>
    return (
      <SegmentSpan segmentId={Number(id)} status={status} first={data['data-segment-first'] === 'true'}>
        {children}
      </SegmentSpan>
    )
  },
}

// Each status is told apart by its underline style as well as its color —
// solid, wavy, dotted — so the distinction never rests on color alone.
const SEGMENT_STYLES: Record<SegmentStatus, CSSProperties> = {
  supported: { background: 'var(--green-bg)', textDecoration: 'underline solid var(--green)' },
  unsupported: { background: 'var(--red-bg)', textDecoration: 'underline wavy var(--red)' },
  unevaluated: { background: 'var(--gray-light-bg)', textDecoration: 'underline dotted var(--gray-light)' },
}

const SEGMENT_LABELS: Record<SegmentStatus, string> = {
  supported: 'Passage étayé par les sources citées',
  unsupported: 'Passage contenant une affirmation non étayée',
  unevaluated: 'Passage non entièrement vérifié',
}

type SpanProps = ComponentPropsWithoutRef<'span'> & { node?: unknown }

// Which sentence's popover is open, and how to open one — read by every
// SegmentSpan through context rather than baked into the `components` map
// passed to ReactMarkdown: a new map on each open would give `span` a new
// component type, remounting every sentence (losing focus and detaching the
// popover's anchor element).
interface SegmentPopoverState {
  openSegmentId: number | null
  onOpen: (segmentId: number, anchor: HTMLElement) => void
}
const SegmentPopoverContext = createContext<SegmentPopoverState>({ openSegmentId: null, onOpen: () => {} })

interface SegmentSpanProps {
  segmentId: number
  status: SegmentStatus
  first: boolean
  children?: ReactNode
}

// One run of a checked sentence (lib/segmentPlugin.ts may split a sentence
// into several runs around markdown formatting). Every run opens the
// sentence's popover; only the first is a keyboard stop. A click on a
// citation link inside the sentence navigates instead of opening it.
function SegmentSpan({ segmentId, status, first, children }: SegmentSpanProps) {
  const { openSegmentId, onOpen } = useContext(SegmentPopoverContext)
  const active = openSegmentId === segmentId
  const open = (e: MouseEvent<HTMLSpanElement>) => {
    if ((e.target as Element).closest('a')) return
    onOpen(segmentId, e.currentTarget)
  }
  const onKeyDown = (e: KeyboardEvent<HTMLSpanElement>) => {
    if (e.key !== 'Enter' && e.key !== ' ') return
    e.preventDefault()
    onOpen(segmentId, e.currentTarget)
  }
  return (
    <span
      data-segment-id={segmentId}
      data-segment-status={status}
      role={first ? 'button' : undefined}
      tabIndex={first ? 0 : undefined}
      aria-label={first ? SEGMENT_LABELS[status] : undefined}
      aria-haspopup={first ? 'dialog' : undefined}
      aria-expanded={first ? active : undefined}
      onClick={open}
      onKeyDown={first ? onKeyDown : undefined}
      className="cursor-pointer rounded-sm"
      style={{
        ...SEGMENT_STYLES[status],
        textDecorationThickness: '1.5px',
        textUnderlineOffset: '3px',
        boxDecorationBreak: 'clone',
        WebkitBoxDecorationBreak: 'clone',
        boxShadow: active ? '0 0 0 1.5px var(--ink-3)' : undefined,
      }}
    >
      {children}
    </span>
  )
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
  const claims = useMemo(() => evaluation?.faithfulness.claims ?? [], [evaluation])
  const hasFlaggedClaims = claims.some((c) => c.supported === false)
  // A claim whose verdict couldn't be obtained also keeps should_auto_expand
  // false (src/generation/guardrail.py): the answer wasn't fully checked.
  const hasUnevaluatedClaims = claims.some((c) => c.supported === null)

  // Answer sentences colored by their claims' verdicts (lib/segmentVerdicts.ts).
  // Sentences with no claim, and evaluations persisted before segments
  // existed (no `segments`, no `segment_id`), stay uncolored.
  const claimsBySegment = useMemo(() => groupClaimsBySegment(claims), [claims])
  const statusBySegment = useMemo(() => {
    const statuses = new Map<number, SegmentStatus>()
    for (const segment of evaluation?.faithfulness.segments ?? []) {
      const status = segmentStatus(claimsBySegment.get(segment.id) ?? [])
      if (status) statuses.set(segment.id, status)
    }
    return statuses
  }, [evaluation, claimsBySegment])
  const hasColoredSegments = statusBySegment.size > 0

  const [openSegment, setOpenSegment] = useState<{ id: number; anchor: HTMLElement } | null>(null)
  const openSegmentPopover = useCallback(
    (id: number, anchor: HTMLElement) =>
      setOpenSegment((current) => (current?.id === id ? null : { id, anchor })),
    [],
  )
  const closeSegmentPopover = useCallback((returnFocus: boolean) => {
    setOpenSegment((current) => {
      if (returnFocus && current) {
        const root = current.anchor.closest('[data-testid="answer-content"]')
        root?.querySelector<HTMLElement>(`[data-segment-id="${current.id}"][tabindex]`)?.focus()
      }
      return null
    })
  }, [])
  const popoverState = useMemo(
    () => ({ openSegmentId: openSegment?.id ?? null, onOpen: openSegmentPopover }),
    [openSegment, openSegmentPopover],
  )
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
    !!evaluation && claims.length > 0 && !hasFlaggedClaims && !hasUnevaluatedClaims && !hasStructuralFlags
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
          ? 'Au moins une affirmation n’a pas été retrouvée dans les sources citées : à relire avant de faire confiance à la réponse.'
          : hasUnevaluatedClaims
            ? 'Certaines affirmations n’ont pas pu être vérifiées.'
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

  // Sentence coloring runs first, while every text leaf still carries its
  // source position (lib/segmentPlugin.ts relies on it); linkification then
  // runs over whatever text leaves remain, including inside the sentence
  // spans — this is what makes a citation bracket inside a checked sentence
  // still become a link nested inside it rather than one transform
  // clobbering the other (explicit regression test, AnswerCard.test.tsx). Citation links are gated on `evaluation` being
  // present at all (no evaluation yet = no confirmed exists-in-input-set
  // result to gate on, so nothing is linked) and on `conversationId`/
  // `turnId` being known (needed to build Screen 4's route).
  const rehypePlugins: PluggableList = []
  if (hasColoredSegments) {
    rehypePlugins.push([rehypeSegments, answer, evaluation!.faithfulness.segments, statusBySegment])
  }
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
        <SegmentPopoverContext.Provider value={popoverState}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={rehypePlugins}
            components={markdownComponents}
          >
            {answer}
          </ReactMarkdown>
        </SegmentPopoverContext.Provider>
      </div>

      {expanded && hasColoredSegments && (
        <p className="mt-3 flex items-start gap-1.5 text-xs" style={{ color: 'var(--gray-dark)' }}>
          <IconInfoCircle size={14} className="mt-0.5 shrink-0" />
          <span>
            Cliquez sur un passage pour voir le détail de sa vérification :{' '}
            <span style={SEGMENT_STYLES.supported}>étayé</span>,{' '}
            <span style={SEGMENT_STYLES.unsupported}>non retrouvé dans les sources</span>,{' '}
            <span style={SEGMENT_STYLES.unevaluated}>non vérifié</span>.
          </span>
        </p>
      )}

      {expanded && hasFlaggedClaims && !hasColoredSegments && (
        <p className="mt-3 flex items-start gap-1.5 text-xs" style={{ color: 'var(--gray-dark)' }}>
          <IconInfoCircle size={14} className="mt-0.5 shrink-0" />
          <span>Au moins une affirmation n’a pas été retrouvée dans les sources citées.</span>
        </p>
      )}

      {expanded && openSegment && (
        <SegmentPopover
          claims={claimsBySegment.get(openSegment.id) ?? []}
          anchor={openSegment.anchor}
          onClose={closeSegmentPopover}
        />
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
