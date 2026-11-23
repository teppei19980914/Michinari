import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { VocabMasteryBreakdownLine } from './VocabMasteryBreakdownLine'

describe('VocabMasteryBreakdownLine', () => {
  it('shows the term/situation breakdown', () => {
    render(
      <VocabMasteryBreakdownLine
        termMastered={2}
        termTotal={7}
        situationMastered={1}
        situationTotal={3}
      />,
    )

    expect(
      screen.getByText(
        t('vocab.deckDetail.masteredCountBreakdown', {
          termMastered: 2,
          termTotal: 7,
          situationMastered: 1,
          situationTotal: 3,
        }),
      ),
    ).toBeTruthy()
  })
})
