import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnswerCard } from './AnswerCard'
import type { EvaluateResponse } from '../api/types'

function makeEvaluation(shouldAutoExpand: boolean): EvaluateResponse {
  return {
    structural: {
      citations: [],
      unknown_citations: [],
      has_citation: true,
      fabricated_titles: [],
      title_year_mismatches: [],
      passed: true,
    },
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
      structural: {
      citations: [],
      unknown_citations: [],
      has_citation: true,
      fabricated_titles: [],
      title_year_mismatches: [],
      passed: true,
    },
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

  // Layer 2 (the faithfulness judge) can score an answer fully supported
  // while missing a Layer 1 title/year failure entirely — the real Q002
  // case that motivated check_title_fabrication
  // (docs/anti_hallucination_guardrails.md). "Fully confirmed" must not be
  // claimed on Layer 2's verdict alone once Layer 1 disagrees, even though
  // this scenario is normally hidden behind the collapsed/blurred state
  // (should_auto_expand already accounts for both flags) — it becomes
  // visible if the user forces a reveal via "Lire quand même".
  it('does not claim full endorsement when Layer 1 flagged a fabricated title, even if every claim is supported', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={{
          structural: {
            citations: [],
            unknown_citations: [],
            has_citation: true,
            fabricated_titles: ['Le comique de caractère'],
            title_year_mismatches: [],
            passed: false,
          },
          faithfulness: {
            score: 1,
            model: 'judge',
            claims: [{ statement: 'A', supported: true, reason: 'ok', quote: null }],
          },
          should_auto_expand: false,
        }}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(
      screen.queryByText('Réponse intégralement confirmée par les passages cités.'),
    ).not.toBeInTheDocument()
  })

  it('does not claim full endorsement when Layer 1 flagged a title/year mismatch, even if every claim is supported', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={{
          structural: {
            citations: [],
            unknown_citations: [],
            has_citation: true,
            fabricated_titles: [],
            title_year_mismatches: [
              { title: "L'évolution créatrice", work_id: '1907_EC', correct_year: 1907, claimed_years: [1934] },
            ],
            passed: false,
          },
          faithfulness: {
            score: 1,
            model: 'judge',
            claims: [{ statement: 'A', supported: true, reason: 'ok', quote: null }],
          },
          should_auto_expand: false,
        }}
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

describe('AnswerCard markdown rendering', () => {
  function evaluationWithClaims(claims: EvaluateResponse['faithfulness']['claims']): EvaluateResponse {
    return {
      structural: {
        citations: [],
        unknown_citations: [],
        has_citation: true,
        fabricated_titles: [],
        title_year_mismatches: [],
        passed: true,
      },
      faithfulness: { score: claims.every((c) => c.supported) ? 1 : 0.5, model: 'judge', claims },
      should_auto_expand: true,
    }
  }

  it('renders markdown syntax (bold, list) as formatted elements, not raw text', () => {
    const { container } = render(
      <AnswerCard
        answer={'**Bergson** distingue deux notions :\n\n- la durée\n- le temps spatialisé'}
        evaluation={null}
        evaluationStatus="idle"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(container.querySelector('strong')?.textContent).toBe('Bergson')
    const items = container.querySelectorAll('li')
    expect(items).toHaveLength(2)
    expect(items[0].textContent).toBe('la durée')
    expect(items[1].textContent).toBe('le temps spatialisé')
    // Not shown as literal, un-rendered markdown syntax.
    expect(screen.queryByText(/\*\*Bergson\*\*/)).not.toBeInTheDocument()
  })

  // The specific regression case named in the task: a flagged claim's
  // verbatim quote falling entirely inside a bolded run must still render
  // both the <strong> formatting and the <mark> highlight, nested rather
  // than one clobbering the other.
  it('renders the faithfulness highlight inside a bolded phrase', () => {
    const { container } = render(
      <AnswerCard
        answer="**Bergson est né à Paris en 1859** selon sa biographie officielle."
        evaluation={evaluationWithClaims([
          { statement: 'x', supported: false, reason: 'non étayé', quote: 'né à Paris en 1859' },
        ])}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    const strong = container.querySelector('strong')
    expect(strong).not.toBeNull()
    const mark = strong!.querySelector('mark')
    expect(mark?.textContent).toBe('né à Paris en 1859')
    // The bold formatting survives around the highlighted span.
    expect(strong!.textContent).toBe('Bergson est né à Paris en 1859')
  })

  // Same regression, inside a list item instead of a bold run.
  it('renders the faithfulness highlight inside a markdown list item', () => {
    const { container } = render(
      <AnswerCard
        answer={'Deux points :\n\n- Bergson est né à Paris en 1859.\n- Il meurt en 1941.'}
        evaluation={evaluationWithClaims([
          { statement: 'x', supported: false, reason: 'non étayé', quote: 'né à Paris en 1859' },
        ])}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    const items = container.querySelectorAll('li')
    expect(items).toHaveLength(2)
    const mark = items[0].querySelector('mark')
    expect(mark?.textContent).toBe('né à Paris en 1859')
    expect(items[0].textContent).toBe('Bergson est né à Paris en 1859.')
    // The second item, with no flagged claim, has no highlight.
    expect(items[1].querySelector('mark')).toBeNull()
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
