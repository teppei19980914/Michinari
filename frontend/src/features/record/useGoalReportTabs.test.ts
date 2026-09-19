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
import { makeGoal } from '../../test/fixtures'

describe('useGoalReportTabs', () => {
  it('hides the selector and has no selected goal when there is no ACTIVE goal', () => {
    const { result } = renderHook(() =>
      useGoalReportTabs([makeGoal({ id: 1, status: 'CLOSED_WITH_RESULT' })]),
    )

    expect(result.current.reportableGoals).toEqual([])
    expect(result.current.showGoalSelector).toBe(false)
    expect(result.current.selectedGoalId).toBeNull()
    expect(result.current.selectedGoal).toBeUndefined()
  })

  it('hides the selector but still resolves the single ACTIVE goal by id', () => {
    const goal = makeGoal({ id: 1, status: 'ACTIVE' })
    const { result } = renderHook(() => useGoalReportTabs([goal]))

    expect(result.current.showGoalSelector).toBe(false)
    // タブが無い間はselectedGoalは導出しない(呼び出し側が全件表示するため未使用)。
    expect(result.current.selectedGoal).toBeUndefined()
    expect(result.current.selectedGoalId).toBe(goal.id)
  })

  it('defaults to the first ACTIVE goal and lets the caller switch tabs', () => {
    const goals = [makeGoal({ id: 1, status: 'ACTIVE' }), makeGoal({ id: 2, status: 'ACTIVE' })]
    const { result } = renderHook(() => useGoalReportTabs(goals))

    expect(result.current.showGoalSelector).toBe(true)
    expect(result.current.selectedGoal?.id).toBe(1)

    act(() => {
      result.current.setSelectedGoalId(2)
    })

    expect(result.current.selectedGoal?.id).toBe(2)
  })

  it('excludes non-ACTIVE goals from the selectable set', () => {
    const goals = [
      makeGoal({ id: 1, status: 'ACTIVE' }),
      makeGoal({ id: 2, status: 'DRAFT' }),
      makeGoal({ id: 3, status: 'ACTIVE' }),
    ]
    const { result } = renderHook(() => useGoalReportTabs(goals))

    expect(result.current.reportableGoals.map((goal) => goal.id)).toEqual([1, 3])
  })
})
