import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import {
  IconChevronDown,
  IconChevronUp,
  IconCircleCheck,
  IconCircleX,
  IconHelpCircle,
} from '@tabler/icons-react'
import type { ClaimVerdictOut } from '../api/types'

// Detail of one answer sentence's faithfulness check, opened by clicking
// the sentence (components/AnswerCard.tsx): every claim the judge drew from
// it, each marked supported / unsupported / not evaluated by an icon *and*
// a color (never color alone), in extraction order — which follows the
// sentence. Clicking a claim discloses the judge's own reason, labeled as
// such: it is a 7B model's explanation, observed to be wrong at times, not
// an established fact. A sentence with a single claim shows its reason
// straight away.
//
// Portaled to <body> with fixed positioning: AnswerCard clips its own
// overflow (for the blurred, collapsed state), which would cut off a
// popover opened on the answer's last lines. Closes on Escape (returning
// focus to the sentence), on a click outside, and on scroll/resize, since a
// fixed panel would otherwise drift away from its sentence.

const CLAIM_META = {
  supported: { Icon: IconCircleCheck, color: 'var(--green)', label: 'Affirmation étayée' },
  unsupported: { Icon: IconCircleX, color: 'var(--red)', label: 'Affirmation non étayée' },
  unevaluated: { Icon: IconHelpCircle, color: 'var(--gray-light)', label: 'Affirmation non vérifiée' },
} as const

function claimKind(claim: ClaimVerdictOut): keyof typeof CLAIM_META {
  if (claim.supported === true) return 'supported'
  if (claim.supported === false) return 'unsupported'
  return 'unevaluated'
}

const MARGIN = 16
const GAP = 6

interface SegmentPopoverProps {
  claims: readonly ClaimVerdictOut[]
  anchor: HTMLElement
  onClose: (returnFocus: boolean) => void
}

export function SegmentPopover({ claims, anchor, onClose }: SegmentPopoverProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState<CSSProperties>({ visibility: 'hidden' })

  // Below the sentence, flipped above it if it would overflow the viewport;
  // horizontally clamped to the viewport's side gutters.
  useLayoutEffect(() => {
    const panel = panelRef.current
    if (!panel) return
    const rect = anchor.getBoundingClientRect()
    const { width, height } = panel.getBoundingClientRect()
    const below = rect.bottom + GAP
    const top =
      below + height > window.innerHeight - MARGIN && rect.top - GAP - height >= MARGIN
        ? rect.top - GAP - height
        : below
    const left = Math.max(MARGIN, Math.min(rect.left, window.innerWidth - MARGIN - width))
    setPosition({ top, left })
  }, [anchor])

  useEffect(() => {
    panelRef.current?.focus({ preventScroll: true })
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose(true)
    }
    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node
      if (!panelRef.current?.contains(target) && !anchor.contains(target)) onClose(false)
    }
    const onViewportChange = () => onClose(false)
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('scroll', onViewportChange, true)
    window.addEventListener('resize', onViewportChange)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('scroll', onViewportChange, true)
      window.removeEventListener('resize', onViewportChange)
    }
  }, [anchor, onClose])

  return createPortal(
    <div
      ref={panelRef}
      role="dialog"
      aria-label="Vérification de ce passage"
      tabIndex={-1}
      data-testid="segment-popover"
      className="fixed z-50 w-[min(24rem,calc(100vw-32px))] rounded-lg p-3 text-sm shadow-lg outline-none"
      style={{ ...position, background: 'var(--paper)', border: '0.5px solid var(--hairline)', color: 'var(--ink)' }}
    >
      <p className="mb-2 text-xs" style={{ color: 'var(--ink-2)' }}>
        Vérification de ce passage
      </p>
      <ul className="flex flex-col gap-1.5">
        {claims.map((claim, i) => (
          <ClaimRow key={i} claim={claim} defaultOpen={claims.length === 1} />
        ))}
      </ul>
    </div>,
    document.body,
  )
}

function ClaimRow({ claim, defaultOpen }: { claim: ClaimVerdictOut; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const { Icon, color, label } = CLAIM_META[claimKind(claim)]
  const icon = <Icon size={16} className="mt-0.5 shrink-0" style={{ color }} aria-label={label} role="img" />

  if (claim.supported === null) {
    return (
      <li className="flex items-start gap-2" data-testid="segment-claim">
        {icon}
        <div>
          <p>{claim.statement}</p>
          <p className="mt-0.5 text-xs" style={{ color: 'var(--ink-2)' }}>
            Vérification impossible pour cette affirmation.
          </p>
        </div>
      </li>
    )
  }

  const Chevron = open ? IconChevronUp : IconChevronDown
  return (
    <li data-testid="segment-claim">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-2 rounded text-left"
      >
        {icon}
        <span className="flex-1">{claim.statement}</span>
        <Chevron size={14} className="mt-1 shrink-0" style={{ color: 'var(--ink-3)' }} aria-hidden />
      </button>
      {open && (
        <div
          className="mt-1 ml-6 border-l-2 pl-2 text-xs"
          style={{ borderColor: 'var(--hairline)', color: 'var(--ink-2)' }}
          data-testid="segment-claim-reason"
        >
          <span className="font-medium">Justification du juge : </span>
          {claim.reason}
        </div>
      )}
    </li>
  )
}
