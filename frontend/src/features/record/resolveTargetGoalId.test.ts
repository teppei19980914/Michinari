import { describe, expect, it } from 'vitest'
import type { GoalRead } from '../../api/goals'
import type { GoalReportTabs } from './useGoalReportTabs'
import { resolveTargetGoalId } from './resolveTargetGoalId'

function makeGoal(id: number, overrides: Partial<GoalRead> = {}): GoalRead {
  return {
    id,
    category: 'EXAM',
    name: `目標${id}`,
    start_date: '2026-01-01',
    status: 'ACTIVE',
    resource_ratio: 0,
    memo: null,
    activated_at: null,
    closed_at: null,
    archived_at: null,
    ...overrides,
  }
}

function makeTabs(overrides: Partial<GoalReportTabs>): GoalReportTabs {
  return {
    reportableGoals: [],
    showGoalSelector: false,
    selectedGoalId: null,
    setSelectedGoalId: () => undefined,
    selectedGoal: undefined,
    ...overrides,
  }
}

describe('resolveTargetGoalId', () => {
  it('着手中の目標が0件のときnullを返す', () => {
    expect(resolveTargetGoalId(makeTabs({ reportableGoals: [] }))).toBeNull()
  })

  it('着手中の目標が1件のとき、タブ非表示のままその目標を返す', () => {
    const goal = makeGoal(1)
    expect(
      resolveTargetGoalId(makeTabs({ reportableGoals: [goal], showGoalSelector: false })),
    ).toBe(1)
  })

  it('着手中の目標が2件以上のとき、選択中の目標を返す', () => {
    const goals = [makeGoal(1), makeGoal(2)]
    expect(
      resolveTargetGoalId(
        makeTabs({ reportableGoals: goals, showGoalSelector: true, selectedGoal: goals[1] }),
      ),
    ).toBe(2)
  })

  it('着手中の目標が2件以上でも未選択のときはnullを返す', () => {
    const goals = [makeGoal(1), makeGoal(2)]
    expect(
      resolveTargetGoalId(
        makeTabs({ reportableGoals: goals, showGoalSelector: true, selectedGoal: undefined }),
      ),
    ).toBeNull()
  })
})
