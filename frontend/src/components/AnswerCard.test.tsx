import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnswerCard } from './AnswerCard'
import type { EvaluateResponse } from '../api/types'

function makeEvaluation(shouldAutoExpand: boolean): EvaluateResponse {
  return {
    structural: { citations: [], unknown_citations: [], has_citation: true, passed: true },
    faithfulness: { score: 1, model: 'judge', claims: [] },
    should_auto_expand: shouldAutoExpand,
  }
}

describe('AnswerCard collapsed state', () => {
  it.each<[boolean]>([[true], [false]])(
    'always renders collapsed first regardless of should_auto_expand (%s)',
    (hasEvaluation) => {
      render(
        <AnswerCard
          answer="Une réponse."
          evaluation={hasEvaluation ? makeEvaluation(false) : null}
          evaluationStatus={hasEvaluation ? 'done' : 'idle'}
          revealed={false}
          onReveal={() => {}}
        />,
      )
      expect(screen.getByText('Lire quand même')).toBeInTheDocument()
      expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'blur(5px)' })
    },
  )
})

describe('AnswerCard confidence gauge removal', () => {
  it('never renders the confidence gauge, expanded or collapsed', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={makeEvaluation(true)}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'none' })
    expect(screen.queryByText('Confiance du retrieval')).not.toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /Confiance :/ })).not.toBeInTheDocument()
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

  it('applies faithfulness annotations once evaluation resolves, without re-blurring', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={makeEvaluation(false)}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(screen.getByTestId('answer-content')).toHaveStyle({ filter: 'none' })
    expect(screen.queryByText('Confiance du retrieval')).not.toBeInTheDocument()
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

describe('AnswerCard full-endorsement statement', () => {
  function evaluationWithClaims(claims: EvaluateResponse['faithfulness']['claims']): EvaluateResponse {
    return {
      structural: { citations: [], unknown_citations: [], has_citation: true, passed: true },
      faithfulness: { score: claims.every((c) => c.supported) ? 1 : 0.5, model: 'judge', claims },
      should_auto_expand: claims.every((c) => c.supported),
    }
  }

  it('states explicitly that the answer is fully endorsed once every claim is supported', () => {
    render(
      <AnswerCard
        answer="Une réponse fondée."
        evaluation={evaluationWithClaims([
          { statement: 'A', supported: true, reason: 'ok', quote: null },
          { statement: 'B', supported: true, reason: 'ok', quote: null },
        ])}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(screen.getByText('Réponse intégralement confirmée par les passages cités.')).toBeInTheDocument()
    expect(screen.queryByText(/non retrouvé tel quel/)).not.toBeInTheDocument()
  })

  it('does not claim full endorsement when a claim is unsupported', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={evaluationWithClaims([
          { statement: 'A', supported: true, reason: 'ok', quote: null },
          { statement: 'B', supported: false, reason: 'non étayé', quote: null },
        ])}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(
      screen.queryByText('Réponse intégralement confirmée par les passages cités.'),
    ).not.toBeInTheDocument()
  })

  it('does not claim full endorsement when no claims were extracted', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={evaluationWithClaims([])}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(
      screen.queryByText('Réponse intégralement confirmée par les passages cités.'),
    ).not.toBeInTheDocument()
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
