import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { VocabMasteryRoadmapSection } from './VocabMasteryRoadmapSection'
import type { RoadmapVocabMasteryRead } from '../../api/goals'

describe('VocabMasteryRoadmapSection', () => {
  it('shows the mastered/total count and the remaining count to the next milestone', () => {
    const vocabMastery: RoadmapVocabMasteryRead = {
      mastered_count: 3,
      total_count: 10,
      remaining_to_next_milestone: 2,
      term_mastered_count: 2,
      term_total_count: 7,
      situation_mastered_count: 1,
      situation_total_count: 3,
    }
    render(<VocabMasteryRoadmapSection vocabMastery={vocabMastery} />)

    expect(
      screen.getByText(t('goals.roadmap.vocabMastery.countLabel', { mastered: 3, total: 10 })),
    ).toBeDefined()
    expect(
      screen.getByText(t('goals.roadmap.vocabMastery.remainingLabel', { count: 2 })),
    ).toBeDefined()
    expect(
      screen.getByText(
        t('vocab.deckDetail.masteredCountBreakdown', {
          termMastered: 2,
          termTotal: 7,
          situationMastered: 1,
          situationTotal: 3,
        }),
      ),
    ).toBeDefined()
  })

  it('shows the all-milestones-reached message when there is no next milestone', () => {
    const vocabMastery: RoadmapVocabMasteryRead = {
      mastered_count: 500,
      total_count: 500,
      remaining_to_next_milestone: null,
      term_mastered_count: 400,
      term_total_count: 400,
      situation_mastered_count: 100,
      situation_total_count: 100,
    }
    render(<VocabMasteryRoadmapSection vocabMastery={vocabMastery} />)

    expect(screen.getByText(t('goals.roadmap.vocabMastery.allMilestonesReached'))).toBeDefined()
  })

  it('does not divide by zero when there are no cards at all', () => {
    const vocabMastery: RoadmapVocabMasteryRead = {
      mastered_count: 0,
      total_count: 0,
      remaining_to_next_milestone: null,
      term_mastered_count: 0,
      term_total_count: 0,
      situation_mastered_count: 0,
      situation_total_count: 0,
    }
    render(<VocabMasteryRoadmapSection vocabMastery={vocabMastery} />)

    expect(
      screen.getByText(t('goals.roadmap.vocabMastery.countLabel', { mastered: 0, total: 0 })),
    ).toBeDefined()
  })
})
