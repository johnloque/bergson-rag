import type { ReactNode } from 'react'
import {
  IconAdjustmentsHorizontal,
  IconChartArrowsVertical,
  IconDice5,
  IconEye,
  IconMessage2,
  IconMessageOff,
  IconSparkles,
} from '@tabler/icons-react'
import { DashedLine } from '../components/DashedConnector'

interface StepData {
  n: 1 | 2 | 4
  side: 'left' | 'right'
  icon: ReactNode
  title: string
  body: string
}

// Steps 1, 2, 4 alternate either side of the vertical spine. Step 3 (below)
// deliberately breaks this rhythm — see Step3Card.
const STEPS: StepData[] = [
  {
    n: 1,
    side: 'left',
    icon: <IconMessage2 size={15} style={{ color: 'var(--red)' }} />,
    title: '1 · Poser une question',
    body: 'Une phrase complète (« En quoi la métaphore de la boule de neige représente-t-elle la conception bergsonienne du changement ? ») ou de simples mots-clés (« religion statique dynamique »).',
  },
  {
    n: 2,
    side: 'right',
    icon: <IconAdjustmentsHorizontal size={15} style={{ color: 'var(--red)' }} />,
    title: '2 · Filtrer les sources (optionnel)',
    body: "Tout le corpus est considéré par défaut. Restreignez par œuvre, ou par période — mode « Publication », ou « Texte » pour dater individuellement les textes de L'Énergie spirituelle et de La Pensée et le Mouvant.",
  },
]

const STEP_4: StepData = {
  n: 4,
  side: 'left',
  icon: <IconSparkles size={15} style={{ color: 'var(--red)' }} />,
  title: '4 · Générer la réponse',
  body: "La synthèse porte sur les paragraphes inclus à l'étape 3. Elle reste voilée (mais lisible) jusqu'à son évaluation, qui repère les risques d'hallucination. Sélectionnez d'autres paragraphes et régénérez à volonté.",
}

function StepMarker({ icon }: { icon: ReactNode }) {
  return (
    <div
      className="flex h-8 w-8 items-center justify-center rounded-full"
      style={{ background: 'var(--paper)', border: '1.5px solid var(--red)' }}
    >
      {icon}
    </div>
  )
}

// One row of the 3-column spine layout (content / 40px icon column /
// content) — the empty side alternates with `step.side` so the icon column
// always sits on the vertical DashedLine running behind every row.
function StepRow({ step }: { step: StepData }) {
  const content = (
    <div className="flex flex-col gap-1">
      <p className="text-sm font-medium" style={{ color: 'var(--ink)' }}>
        {step.title}
      </p>
      <p className="text-xs" style={{ color: 'var(--ink-2)' }}>
        {step.body}
      </p>
    </div>
  )

  return (
    <div
      data-testid={`guide-step-${step.n}`}
      data-side={step.side}
      className="relative z-10 grid grid-cols-[1fr_40px_1fr] items-center gap-6"
    >
      {step.side === 'left' ? content : <div />}
      <div className="flex justify-center">
        <StepMarker icon={step.icon} />
      </div>
      {step.side === 'right' ? content : <div />}
    </div>
  )
}

// Step 3 breaks the alternating rhythm on purpose — a full-width card, not
// constrained to a left/right column, since it covers more ground
// (inspecting, explaining, navigating neighbors, including/excluding) than
// the single-sentence steps around it.
function Step3Card() {
  return (
    <div
      data-testid="guide-step-3"
      className="relative z-10 mx-[60px] flex flex-col gap-3 rounded-xl px-6 py-6"
      style={{ background: 'var(--paper-2)' }}
    >
      <div className="flex items-center gap-2">
        <IconEye size={18} style={{ color: 'var(--red)' }} />
        <p className="text-sm font-medium" style={{ color: 'var(--ink)' }}>
          3 · Analyser les passages récupérés
        </p>
      </div>
      <ul className="flex list-disc flex-col gap-1 pl-5 text-[12.5px] leading-[1.8]" style={{ color: 'var(--ink-2)' }}>
        <li>
          Un rail affiche les paragraphes triés par score de similarité, avec un indicateur de
          confiance du retrieval.
        </li>
        <li>Inspectez le contenu de chacun, demandez une explication de sa pertinence.</li>
        <li>Naviguez vers les paragraphes voisins dans le corpus, inspectables de la même façon.</li>
        <li>
          Incluez/excluez jusqu'à 5 paragraphes (les 3 premiers sont sélectionnés par défaut) — un
          second rail distingue les paragraphes voisins ajoutés de ceux issus de la recherche.
        </li>
      </ul>
    </div>
  )
}

// Full content and layout for the sidebar's "Guide d'utilisation" sub-page
// (docs/frontend.md) — supersedes the earlier short-paragraph placeholder
// from `feat/sidebar-restructure`.
export function GuideUtilisation() {
  return (
    <div className="mx-auto max-w-3xl px-10 py-10">
      <div className="mb-10 flex flex-col items-center gap-2 text-center">
        <p
          className="font-wordmark text-[13px] uppercase"
          style={{ color: 'var(--ink-3)', letterSpacing: '2px' }}
        >
          Guide d'utilisation
        </p>
        <p className="font-wordmark text-[22px] font-medium" style={{ color: 'var(--ink)' }}>
          Quatre étapes, du premier mot à la synthèse
        </p>
      </div>

      <div className="relative flex flex-col gap-10">
        <DashedLine orientation="vertical" className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2" />
        <StepRow step={STEPS[0]} />
        <StepRow step={STEPS[1]} />
        <Step3Card />
        <StepRow step={STEP_4} />
      </div>

      {/* Deliberately neutral (--ink-3 icons, no red): these are honest
          limitations, not steps to follow, and must not visually compete
          with the numbered sequence above. */}
      <div className="mt-10 pt-8" style={{ borderTop: '0.5px solid var(--hairline)' }}>
        <div data-testid="guide-closeout" className="grid grid-cols-3 gap-6">
          <div className="flex flex-col items-center gap-2 text-center">
            <IconMessageOff size={16} style={{ color: 'var(--ink-3)' }} />
            <p className="text-[11.5px]" style={{ color: 'var(--ink-2)' }}>
              Chaque question d'une conversation est traitée indépendamment, sans mémoire des
              précédentes.
            </p>
          </div>
          <div className="flex flex-col items-center gap-2 text-center">
            <IconDice5 size={16} style={{ color: 'var(--ink-3)' }} />
            <p className="text-[11.5px]" style={{ color: 'var(--ink-2)' }}>
              Une réponse n'est pas déterministe, ni jamais parfaite — même sans hallucination
              détectée.
            </p>
          </div>
          <div className="flex flex-col items-center gap-2 text-center">
            <IconChartArrowsVertical size={16} style={{ color: 'var(--ink-3)' }} />
            <p className="text-[11.5px]" style={{ color: 'var(--ink-2)' }}>
              La performance varie selon les questions — certaines réponses sont dispersées
              au-delà de ce que couvre le retrieval.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
