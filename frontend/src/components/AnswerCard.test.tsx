import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnswerCard } from './AnswerCard'
import type { EvaluateResponse, RetrievalConfidenceTier } from '../api/types'

function makeEvaluation(
  tier: RetrievalConfidenceTier,
  shouldAutoExpand: boolean,
): EvaluateResponse {
  return {
    structural: { citations: [], unknown_citations: [], has_citation: true, passed: true },
    faithfulness: { score: 1, model: 'judge', claims: [] },
    retrieval_confidence_tier: tier,
    should_auto_expand: shouldAutoExpand,
  }
}

describe('AnswerCard collapsed state', () => {
  it.each<[RetrievalConfidenceTier | null]>([
    ['très faible'],
    ['faible'],
    ['moyenne'],
    ['élevée'],
    [null],
  ])('always renders collapsed first regardless of confidence tier (%s)', (tier) => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={tier ? makeEvaluation(tier, false) : null}
        evaluationStatus={tier ? 'done' : 'idle'}
        revealed={false}
        onReveal={() => {}}
      />,
    )
    expect(screen.getByText('Lire quand même')).toBeInTheDocument()
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'blur(5px)' })
  })
})

describe('AnswerCard reveal behavior', () => {
  it('un-blurs immediately on "Lire quand même" without an evaluation yet', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={null}
        evaluationStatus="pending"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(screen.queryByText('Lire quand même')).not.toBeInTheDocument()
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'none' })
    expect(screen.queryByText('Confiance du retrieval')).not.toBeInTheDocument()
  })

  it('applies confidence/annotations once evaluation resolves, without re-blurring', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={makeEvaluation('moyenne', false)}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'none' })
    expect(screen.getByText('Confiance du retrieval')).toBeInTheDocument()
  })

  it('calls onReveal when the button is clicked', () => {
    const onReveal = vi.fn()
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={null}
        evaluationStatus="idle"
        revealed={false}
        onReveal={onReveal}
      />,
    )
    screen.getByText('Lire quand même').click()
    expect(onReveal).toHaveBeenCalledOnce()
  })
})

describe('AnswerCard evaluation failure', () => {
  it('never shows "Vérifié" when /evaluate errored, and offers a retry', () => {
    const onEvaluate = vi.fn()
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={null}
        evaluationStatus="error"
        revealed={false}
        onReveal={() => {}}
        onEvaluate={onEvaluate}
      />,
    )
    expect(screen.queryByText('Vérifié')).not.toBeInTheDocument()
    expect(screen.getByText('Vérification indisponible')).toBeInTheDocument()
    screen.getByText('Réessayer la vérification').click()
    expect(onEvaluate).toHaveBeenCalledOnce()
  })
})

describe('AnswerCard manual evaluation trigger', () => {
  it('offers an "Évaluer" button once the answer is generated, and never auto-runs', () => {
    const onEvaluate = vi.fn()
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={null}
        evaluationStatus="idle"
        revealed={false}
        onReveal={() => {}}
        onEvaluate={onEvaluate}
      />,
    )
    screen.getByText('Évaluer').click()
    expect(onEvaluate).toHaveBeenCalledOnce()
  })

  it('hides the "Évaluer" button while an evaluation is already in flight', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={null}
        evaluationStatus="pending"
        revealed={false}
        onReveal={() => {}}
        onEvaluate={() => {}}
      />,
    )
    expect(screen.queryByText('Évaluer')).not.toBeInTheDocument()
  })
})
