import { describe, expect, it } from 'vitest'
import type { GoalRead } from '../../api/goals'
import { isSectionVisible, type GoalTabState } from './sectionVisibility'

const READING_GOAL = { id: 1, category: 'READING' } as GoalRead

const WITHOUT_TABS: GoalTabState = { showGoalSelector: false, selectedGoal: undefined }
const READING_TAB: GoalTabState = { showGoalSelector: true, selectedGoal: READING_GOAL }
const NO_TAB_SELECTED: GoalTabState = { showGoalSelector: true, selectedGoal: undefined }

describe('isSectionVisible', () => {
  it('shows a category with content when there is no tab bar', () => {
    expect(isSectionVisible(WITHOUT_TABS, 'READING', true)).toBe(true)
  })

  it('hides a category without content when there is no tab bar', () => {
    expect(isSectionVisible(WITHOUT_TABS, 'READING', false)).toBe(false)
  })

  it('shows the selected category', () => {
    expect(isSectionVisible(READING_TAB, 'READING', true)).toBe(true)
  })

  it('hides the categories the selected tab does not point at', () => {
    expect(isSectionVisible(READING_TAB, 'EXAM', true)).toBe(false)
    expect(isSectionVisible(READING_TAB, 'WORK', true)).toBe(false)
  })

  it('hides the selected category when it has no content', () => {
    expect(isSectionVisible(READING_TAB, 'READING', false)).toBe(false)
  })

  it('hides everything while no tab is selected yet', () => {
    expect(isSectionVisible(NO_TAB_SELECTED, 'READING', true)).toBe(false)
  })
})
