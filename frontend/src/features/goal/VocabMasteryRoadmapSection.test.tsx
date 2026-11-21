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
    }
    render(<VocabMasteryRoadmapSection vocabMastery={vocabMastery} />)

    expect(
      screen.getByText(t('goals.roadmap.vocabMastery.countLabel', { mastered: 3, total: 10 })),
    ).toBeDefined()
    expect(
      screen.getByText(t('goals.roadmap.vocabMastery.remainingLabel', { count: 2 })),
    ).toBeDefined()
  })

  it('shows the all-milestones-reached message when there is no next milestone', () => {
    const vocabMastery: RoadmapVocabMasteryRead = {
      mastered_count: 500,
      total_count: 500,
      remaining_to_next_milestone: null,
    }
    render(<VocabMasteryRoadmapSection vocabMastery={vocabMastery} />)

    expect(screen.getByText(t('goals.roadmap.vocabMastery.allMilestonesReached'))).toBeDefined()
  })

  it('does not divide by zero when there are no cards at all', () => {
    const vocabMastery: RoadmapVocabMasteryRead = {
      mastered_count: 0,
      total_count: 0,
      remaining_to_next_milestone: null,
    }
    render(<VocabMasteryRoadmapSection vocabMastery={vocabMastery} />)

    expect(
      screen.getByText(t('goals.roadmap.vocabMastery.countLabel', { mastered: 0, total: 0 })),
    ).toBeDefined()
  })
})
