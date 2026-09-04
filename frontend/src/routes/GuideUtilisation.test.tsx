import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { GuideUtilisation } from './GuideUtilisation'

describe('GuideUtilisation', () => {
  it('renders steps 1, 2 and 4 alternating left/right around the spine', () => {
    render(<GuideUtilisation />)

    expect(screen.getByTestId('guide-step-1')).toHaveAttribute('data-side', 'left')
    expect(screen.getByTestId('guide-step-2')).toHaveAttribute('data-side', 'right')
    expect(screen.getByTestId('guide-step-4')).toHaveAttribute('data-side', 'left')

    expect(screen.getByText('1 · Poser une question')).toBeInTheDocument()
    expect(screen.getByText('2 · Filtrer les sources (optionnel)')).toBeInTheDocument()
    expect(screen.getByText('4 · Générer la réponse')).toBeInTheDocument()
  })

  it('renders step 3 as a full-width card, breaking the alternating rhythm, with its four bullet points', () => {
    render(<GuideUtilisation />)

    const step3 = screen.getByTestId('guide-step-3')
    expect(step3).not.toHaveAttribute('data-side')
    expect(step3).toHaveTextContent('3 · Analyser les passages récupérés')

    const bullets = step3.querySelectorAll('li')
    expect(bullets).toHaveLength(4)
    expect(step3).toHaveTextContent('indicateur de confiance du retrieval')
    expect(step3).toHaveTextContent('demandez une explication de sa pertinence')
    expect(step3).toHaveTextContent('paragraphes voisins dans le corpus')
    expect(step3).toHaveTextContent('les 3 premiers sont sélectionnés par défaut')
  })

  it('renders the closing "À garder en tête" section below the step sequence with its three items', () => {
    render(<GuideUtilisation />)

    const closeout = screen.getByTestId('guide-closeout')
    expect(closeout).toHaveTextContent('sans mémoire des')
    expect(closeout).toHaveTextContent("n'est pas déterministe")
    expect(closeout).toHaveTextContent('La performance varie selon les questions')
  })
})
