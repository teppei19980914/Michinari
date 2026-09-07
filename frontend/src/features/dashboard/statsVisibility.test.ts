import { describe, expect, it } from 'vitest'
import type { DashboardRead } from '../../api/dashboard'
import { buildCategoryByGoalId, showsBufferUsageRate } from './statsVisibility'

function makeCard(
  goalId: number,
  category: DashboardRead['goal_cards'][number]['category'],
): DashboardRead['goal_cards'][number] {
  return {
    goal_id: goalId,
    goal_name: `目標${goalId}`,
    category,
    progress_rate: null,
    remaining_days: null,
    forecast_deviation_days: null,
    has_warning: false,
    has_forced_replan: false,
    book: null,
    work_assignment: null,
  }
}

describe('buildCategoryByGoalId', () => {
  it('goal_id からカテゴリを引けるようにする', () => {
    const map = buildCategoryByGoalId([makeCard(1, 'EXAM'), makeCard(2, 'READING')])
    expect(map).toEqual({ 1: 'EXAM', 2: 'READING' })
  })

  it('目標カードが空なら空の対応表を返す', () => {
    expect(buildCategoryByGoalId([])).toEqual({})
  })
})

describe('showsBufferUsageRate', () => {
  it('資格試験目標では表示する', () => {
    expect(showsBufferUsageRate('EXAM')).toBe(true)
  })

  it('読書・仕事目標では表示しない（R-71・R-74）', () => {
    expect(showsBufferUsageRate('READING')).toBe(false)
    expect(showsBufferUsageRate('WORK')).toBe(false)
  })

  it('カテゴリが解決できない場合は表示しない', () => {
    expect(showsBufferUsageRate(undefined)).toBe(false)
  })
})
