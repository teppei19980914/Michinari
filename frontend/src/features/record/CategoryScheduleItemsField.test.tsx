import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { CategoryScheduleItemsField } from './CategoryScheduleItemsField'
import type { GoalScheduleItemsForReportRead } from '../../api/records'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'
import type { DailyReportDraft } from './useDailyReportDraft'

function buildGoal(id: number, name: string): GoalScheduleItemsForReportRead {
  return {
    goal_id: id,
    goal_name: name,
    goal_category: 'EXAM',
    items: [
      {
        id: id * 10,
        title: `作業${id}`,
        planned_start_date: '2026-11-01',
        planned_end_date: '2026-11-10',
        status: 'NOT_STARTED',
        actual_start_date: null,
        actual_end_date: null,
        default_visible: true,
      },
    ],
  }
}

const EXAM_GOAL = buildGoal(1, '資格目標')
const READING_GOAL = buildGoal(2, '読書目標')
const WORK_GOAL = buildGoal(3, '仕事目標')
const EXAM_GOAL_HISTORY = buildGoal(11, '確定済みの資格目標')

const TARGETS = {
  examScheduleItemGoals: [EXAM_GOAL],
  readingScheduleItemGoals: [READING_GOAL],
  workScheduleItemGoals: [WORK_GOAL],
  examScheduleItemHistoryGoals: [EXAM_GOAL_HISTORY],
  readingScheduleItemHistoryGoals: [],
  workScheduleItemHistoryGoals: [],
} as unknown as VisibleReportTargets

const DRAFT = {
  scheduleItemValues: {},
  setScheduleItemValues: vi.fn(),
} as unknown as DailyReportDraft

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('CategoryScheduleItemsField', () => {
  it('selects examScheduleItemGoals for EXAM', () => {
    render(
      <CategoryScheduleItemsField
        category="EXAM"
        targets={TARGETS}
        targetDate="2026-11-05"
        readOnly={false}
        draft={DRAFT}
      />,
    )
    expect(screen.getByText('資格目標')).toBeTruthy()
    expect(screen.queryByText('読書目標')).toBe(null)
  })

  it('selects readingScheduleItemGoals for READING', () => {
    render(
      <CategoryScheduleItemsField
        category="READING"
        targets={TARGETS}
        targetDate="2026-11-05"
        readOnly={false}
        draft={DRAFT}
      />,
    )
    expect(screen.getByText('読書目標')).toBeTruthy()
  })

  it('selects workScheduleItemGoals for WORK', () => {
    render(
      <CategoryScheduleItemsField
        category="WORK"
        targets={TARGETS}
        targetDate="2026-11-05"
        readOnly={false}
        draft={DRAFT}
      />,
    )
    expect(screen.getByText('仕事目標')).toBeTruthy()
  })

  it('readOnly時はexamScheduleItemHistoryGoalsを使う（軽微な修正3）', () => {
    render(
      <CategoryScheduleItemsField
        category="EXAM"
        targets={TARGETS}
        targetDate="2026-11-05"
        readOnly={true}
        draft={DRAFT}
      />,
    )
    expect(screen.getByText('確定済みの資格目標')).toBeTruthy()
    expect(screen.queryByText('資格目標')).toBe(null)
  })
})
