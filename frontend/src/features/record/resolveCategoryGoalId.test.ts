import { describe, expect, it } from 'vitest'
import type { GoalRead } from '../../api/goals'
import { resolveCategoryGoalId } from './resolveCategoryGoalId'

function makeGoal(id: number, overrides: Partial<GoalRead> = {}): GoalRead {
  return {
    id,
    category: 'EXAM',
    name: `目標${id}`,
    start_date: '2026-01-01',
    status: 'ACTIVE',
    memo: null,
    activated_at: null,
    closed_at: null,
    archived_at: null,
    ...overrides,
  }
}

describe('resolveCategoryGoalId', () => {
  it('目標タブ非表示のとき、fallbackGoalIdをそのまま返す', () => {
    expect(resolveCategoryGoalId({ showGoalSelector: false, selectedGoal: undefined }, 'EXAM', 5)).toBe(
      5,
    )
    expect(
      resolveCategoryGoalId({ showGoalSelector: false, selectedGoal: undefined }, 'EXAM', null),
    ).toBeNull()
  })

  it('目標タブ表示中、選択中の目標が指定カテゴリと一致すればその目標のidを返す', () => {
    const goal = makeGoal(1, { category: 'READING' })
    expect(resolveCategoryGoalId({ showGoalSelector: true, selectedGoal: goal }, 'READING', null)).toBe(
      1,
    )
  })

  it('目標タブ表示中、選択中の目標が指定カテゴリと異なればnullを返す(fallbackは無視)', () => {
    const goal = makeGoal(1, { category: 'WORK' })
    expect(
      resolveCategoryGoalId({ showGoalSelector: true, selectedGoal: goal }, 'EXAM', 99),
    ).toBeNull()
  })

  it('目標タブ表示中、未選択(selectedGoal=undefined)ならnullを返す', () => {
    expect(
      resolveCategoryGoalId({ showGoalSelector: true, selectedGoal: undefined }, 'EXAM', null),
    ).toBeNull()
  })
})
