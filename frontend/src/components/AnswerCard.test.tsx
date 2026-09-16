import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom'
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

// `feat/clickable-citations`: a `[chunk_id]` inline citation becomes a
// clickable link to Screen 4 (routes/ChunkDetail.tsx), gated strictly on
// whether Layer 1 (src/generation/guardrail.py's check_structure) confirmed
// that chunk_id is present in the generation's own input chunk set — reused
// directly via `evaluation.structural.unknown_citations`, not recomputed.
describe('AnswerCard citation links', () => {
  function evaluationWith(
    opts: { unknownCitations?: string[]; claims?: EvaluateResponse['faithfulness']['claims'] } = {},
  ): EvaluateResponse {
    const claims = opts.claims ?? []
    return {
      structural: {
        citations: ['1907_EC_c5'],
        unknown_citations: opts.unknownCitations ?? [],
        has_citation: true,
        fabricated_titles: [],
        title_year_mismatches: [],
        passed: (opts.unknownCitations ?? []).length === 0,
      },
      faithfulness: { score: 1, model: 'judge', claims },
      should_auto_expand: true,
    }
  }

  // Renders AnswerCard at /c/1, with Screen 4's real route target next to
  // it, so a click can be asserted to actually land on the right chunk —
  // not just that an <a> with a plausible-looking href exists.
  function renderAtConversation(answer: string, evaluation: EvaluateResponse | null) {
    function ChunkDetailStub() {
      const params = useParams()
      return <div data-testid="screen4">{`${params.conversationId}/${params.turnId}/${params.chunkId}`}</div>
    }
    return render(
      <MemoryRouter initialEntries={['/c/1']}>
        <Routes>
          <Route
            path="/c/:conversationId"
            element={
              <AnswerCard
                answer={answer}
                evaluation={evaluation}
                evaluationStatus="done"
                revealed={true}
                onReveal={() => {}}
                conversationId={1}
                turnId={2}
              />
            }
          />
          <Route path="/c/:conversationId/turn/:turnId/chunk/:chunkId" element={<ChunkDetailStub />} />
        </Routes>
      </MemoryRouter>,
    )
  }

  it('renders a citation confirmed present in the input chunk set as a clickable link, text unchanged', () => {
    renderAtConversation('Une affirmation [1907_EC_c5].', evaluationWith())
    const link = screen.getByTestId('citation-link')
    expect(link.tagName).toBe('A')
    // Regression: the link's text content is the bare chunk_id, exactly as
    // written — never reformatted to the work+year+paragraph citation
    // format used elsewhere (lib/citation.ts's formatCitation).
    expect(link.textContent).toBe('1907_EC_c5')
    // The surrounding brackets stay as plain text, next to the link, so the
    // paragraph still reads "[1907_EC_c5]" overall.
    expect(screen.getByTestId('answer-content').textContent).toBe('Une affirmation [1907_EC_c5].')
  })

  // Restyled from plain red/underlined text to a red pill on direct
  // request (docs/frontend.md's "Styling, revised after initial review") —
  // reuses the same rounded-full `--red-bg`/`--red` pill convention as
  // StatusPill.tsx/RelevancePill.tsx elsewhere in this app.
  it('styles the link as a red pill, not plain underlined text', () => {
    renderAtConversation('Une affirmation [1907_EC_c5].', evaluationWith())
    const link = screen.getByTestId('citation-link')
    expect(link.className).toContain('rounded-full')
    expect(link).toHaveStyle({ background: 'var(--red-bg)', color: 'var(--red)' })
  })

  it('navigates to Screen 4 with the correct chunk focused on click', async () => {
    const user = userEvent.setup()
    renderAtConversation('Une affirmation [1907_EC_c5].', evaluationWith())
    await user.click(screen.getByTestId('citation-link'))
    expect(await screen.findByTestId('screen4')).toHaveTextContent('1/2/1907_EC_c5')
  })

  it('does not link a citation Layer 1 flagged as unknown — existing flag treatment only', () => {
    renderAtConversation('Une affirmation [1907_EC_c5].', evaluationWith({ unknownCitations: ['1907_EC_c5'] }))
    expect(screen.queryByTestId('citation-link')).not.toBeInTheDocument()
    expect(screen.getByTestId('answer-content').textContent).toBe('Une affirmation [1907_EC_c5].')
    expect(
      screen.getByText('La citation [1907_EC_c5] ne correspond à aucun passage fourni.'),
    ).toBeInTheDocument()
  })

  it('does not link anything when there is no evaluation yet (no confirmed exists-in-set result)', () => {
    renderAtConversation('Une affirmation [1907_EC_c5].', null)
    expect(screen.queryByTestId('citation-link')).not.toBeInTheDocument()
  })

  it('renders correctly as both bold and a link when the citation sits inside a bolded phrase', () => {
    renderAtConversation('**Une affirmation [1907_EC_c5]** notable.', evaluationWith())
    const { container } = { container: screen.getByTestId('answer-content') }
    const strong = container.querySelector('strong')
    expect(strong).not.toBeNull()
    const link = strong!.querySelector('a')
    expect(link?.textContent).toBe('1907_EC_c5')
    expect(strong!.textContent).toBe('Une affirmation [1907_EC_c5]')
  })

  it('renders both the faithfulness highlight and the citation link when a flagged quote contains the citation', () => {
    renderAtConversation(
      'Le texte affirme une chose surprenante [1907_EC_c5], à vérifier.',
      evaluationWith({
        claims: [
          {
            statement: 'x',
            supported: false,
            reason: 'non étayé',
            quote: 'une chose surprenante [1907_EC_c5]',
          },
        ],
      }),
    )
    const mark = screen.getByTestId('answer-content').querySelector('mark')
    expect(mark).not.toBeNull()
    const link = mark!.querySelector('a')
    expect(link).not.toBeNull()
    expect(link!.textContent).toBe('1907_EC_c5')
    // Highlight and link compose: the mark still contains the full flagged
    // quote (bracket included), the link nests inside it and doesn't
    // truncate or duplicate any of the surrounding highlighted text.
    expect(mark!.textContent).toBe('une chose surprenante [1907_EC_c5]')
  })

  it('links each known chunk_id independently within a multi-id bracket', () => {
    renderAtConversation(
      'Plusieurs passages convergent [1888_EDIC_c1, 1934_PM_c23].',
      evaluationWith({ unknownCitations: ['1934_PM_c23'] }),
    )
    const links = screen.getAllByTestId('citation-link')
    expect(links).toHaveLength(1)
    expect(links[0].textContent).toBe('1888_EDIC_c1')
    expect(screen.getByTestId('answer-content').textContent).toBe(
      'Plusieurs passages convergent [1888_EDIC_c1, 1934_PM_c23].',
    )
  })
})

// "Vérifié" (StatusPill) only ever means "the check ran and completed" — it
// says nothing about the verdict, so a verified-but-still-collapsed card
// (should_auto_expand false, evaluationStatus 'done') read as contradictory/
// buggy without an explanation (user report, fix/answer-verification): the
// badge says done, the content is still hidden behind "Lire quand même".
// `collapseReason` names the actual reason: a structural flag (Layer 1) or
// an unsupported claim (Layer 2) — the only two things that can make
// should_auto_expand false (src/generation/guardrail.py). Retrieval
// confidence used to be a third gate, inferred here by elimination when
// neither of the other two fired, but no longer gates should_auto_expand
// at all (`fix/answer-verification`'s "Dropped: retrieval confidence as an
// auto-expand gate", docs/anti_hallucination_guardrails.md) — the "neither
// flag fired" case can no longer happen for a real API response, but
// `evaluation` is still a plain prop, so the component doesn't assume that
// invariant and simply shows no reason for a combination it can't explain
// (see the last test below).
describe('AnswerCard collapse reason', () => {
  function evaluation(overrides: {
    fabricatedTitles?: string[]
    titleYearMismatches?: EvaluateResponse['structural']['title_year_mismatches']
    claims?: EvaluateResponse['faithfulness']['claims']
  }): EvaluateResponse {
    return {
      structural: {
        citations: [],
        unknown_citations: [],
        has_citation: true,
        fabricated_titles: overrides.fabricatedTitles ?? [],
        title_year_mismatches: overrides.titleYearMismatches ?? [],
        passed: true,
      },
      faithfulness: { score: 1, model: 'judge', claims: overrides.claims ?? [] },
      should_auto_expand: false,
    }
  }

  it('shows no reason for a should_auto_expand: false evaluation with neither flag fired (not a real API shape, defensive only)', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={evaluation({})}
        evaluationStatus="done"
        revealed={false}
        onReveal={() => {}}
      />,
    )
    expect(screen.queryByTestId('collapse-reason')).not.toBeInTheDocument()
  })

  it('names the unsupported claim when Layer 2 flagged one, even with no structural flag', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={evaluation({
          claims: [{ statement: 'A', supported: false, reason: 'non étayé', quote: null }],
        })}
        evaluationStatus="done"
        revealed={false}
        onReveal={() => {}}
      />,
    )
    expect(screen.getByTestId('collapse-reason').textContent).toMatch(/sources citées/i)
  })

  it('names the structural flag when Layer 1 fired, even with every claim supported', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={evaluation({
          fabricatedTitles: ['Le comique de caractère'],
          claims: [{ statement: 'A', supported: true, reason: 'ok', quote: null }],
        })}
        evaluationStatus="done"
        revealed={false}
        onReveal={() => {}}
      />,
    )
    expect(screen.getByTestId('collapse-reason').textContent).toMatch(/titre ou une date/i)
  })

  it('prefers the structural reason when both a structural and a faithfulness flag fired', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={evaluation({
          fabricatedTitles: ['Le comique de caractère'],
          claims: [{ statement: 'A', supported: false, reason: 'non étayé', quote: null }],
        })}
        evaluationStatus="done"
        revealed={false}
        onReveal={() => {}}
      />,
    )
    expect(screen.getByTestId('collapse-reason').textContent).toMatch(/titre ou une date/i)
  })

  it('does not render once expanded — the reason only makes sense next to the veil', () => {
    render(
      <AnswerCard
        answer="Une réponse."
        evaluation={evaluation({})}
        evaluationStatus="done"
        revealed={true}
        onReveal={() => {}}
      />,
    )
    expect(screen.queryByTestId('collapse-reason')).not.toBeInTheDocument()
  })

  it('does not render before evaluation has actually completed (idle/pending/error)', () => {
    for (const status of ['idle', 'pending', 'error'] as const) {
      const { unmount } = render(
        <AnswerCard
          answer="Une réponse."
          evaluation={null}
          evaluationStatus={status}
          revealed={false}
          onReveal={() => {}}
        />,
      )
      expect(screen.queryByTestId('collapse-reason')).not.toBeInTheDocument()
      unmount()
    }
  })
})
