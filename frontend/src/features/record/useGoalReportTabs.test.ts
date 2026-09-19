/** useGoalReportTabs の回帰テスト。
 *
 * DailyReportPage.test.tsx・CalendarPage.test.tsxは2〜3目標構成でのタブ切替、1件のときの
 * 非表示化は検証しているが、着手中(ACTIVE)の目標が0件のケース（新規利用者・全目標が
 * 下書き/クローズ済みの状態）は一度も直接検証されていなかった（2026-09-19、テスト全般の
 * 抜け漏れ調査で発覚）。分岐が無いほぼ純粋な導出ロジックのため、Provider無しで直接
 * renderHookできる。 */
import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useGoalReportTabs } from './useGoalReportTabs'
import type { GoalRead } from '../../api/goals'

function buildGoal(id: number, status: GoalRead['status']): GoalRead {
  return {
    id,
    category: 'EXAM',
    name: `goal-${id}`,
    start_date: '2026-09-01',
    status,
    memo: null,
    activated_at: null,
    closed_at: null,
    archived_at: null,
  }
}

describe('useGoalReportTabs', () => {
  it('hides the selector and has no selected goal when there is no ACTIVE goal', () => {
    const { result } = renderHook(() => useGoalReportTabs([buildGoal(1, 'CLOSED_WITH_RESULT')]))

    expect(result.current.reportableGoals).toEqual([])
    expect(result.current.showGoalSelector).toBe(false)
    expect(result.current.selectedGoalId).toBeNull()
    expect(result.current.selectedGoal).toBeUndefined()
  })

  it('hides the selector but still resolves the single ACTIVE goal by id', () => {
    const goal = buildGoal(1, 'ACTIVE')
    const { result } = renderHook(() => useGoalReportTabs([goal]))

    expect(result.current.showGoalSelector).toBe(false)
    // タブが無い間はselectedGoalは導出しない(呼び出し側が全件表示するため未使用)。
    expect(result.current.selectedGoal).toBeUndefined()
    expect(result.current.selectedGoalId).toBe(goal.id)
  })

  it('defaults to the first ACTIVE goal and lets the caller switch tabs', () => {
    const goals = [buildGoal(1, 'ACTIVE'), buildGoal(2, 'ACTIVE')]
    const { result } = renderHook(() => useGoalReportTabs(goals))

    expect(result.current.showGoalSelector).toBe(true)
    expect(result.current.selectedGoal?.id).toBe(1)

    act(() => {
      result.current.setSelectedGoalId(2)
    })

    expect(result.current.selectedGoal?.id).toBe(2)
  })

  it('excludes non-ACTIVE goals from the selectable set', () => {
    const goals = [buildGoal(1, 'ACTIVE'), buildGoal(2, 'DRAFT'), buildGoal(3, 'ACTIVE')]
    const { result } = renderHook(() => useGoalReportTabs(goals))

    expect(result.current.reportableGoals.map((goal) => goal.id)).toEqual([1, 3])
  })
})
