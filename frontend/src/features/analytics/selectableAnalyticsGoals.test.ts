import { describe, expect, it } from 'vitest'
import type { GoalRead } from '../../api/goals'
import { hasArchivedAnalyticsGoals, selectableAnalyticsGoals } from './selectableAnalyticsGoals'

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

describe('selectableAnalyticsGoals', () => {
  it('着手中の目標を残す', () => {
    const goals = [makeGoal(1)]
    expect(selectableAnalyticsGoals(goals)).toEqual(goals)
  })

  it('クローズ済みの目標も残す（分析は振り返りにも用いるため）', () => {
    const goals = [makeGoal(1, { status: 'CLOSED_WITH_RESULT' })]
    expect(selectableAnalyticsGoals(goals)).toEqual(goals)
  })

  it('アーカイブ済みの目標を既定では除外する（要件定義書R-61）', () => {
    const goals = [makeGoal(1), makeGoal(2, { archived_at: '2026-09-01T00:00:00' })]
    expect(selectableAnalyticsGoals(goals).map((goal) => goal.id)).toEqual([1])
  })

  it('includeArchivedを指定するとアーカイブ済みの目標も含める（トグルON時）', () => {
    const goals = [makeGoal(1), makeGoal(2, { archived_at: '2026-09-01T00:00:00' })]
    expect(
      selectableAnalyticsGoals(goals, { includeArchived: true }).map((goal) => goal.id),
    ).toEqual([1, 2])
  })

  it('includeArchivedを指定しても下書きは除外する（どのタブも空になるため）', () => {
    const goals = [makeGoal(1, { status: 'DRAFT', archived_at: '2026-09-01T00:00:00' })]
    expect(selectableAnalyticsGoals(goals, { includeArchived: true })).toEqual([])
  })

  it('下書きの目標を除外する（記録が存在せず全タブが空になるため）', () => {
    const goals = [makeGoal(1), makeGoal(2, { status: 'DRAFT' })]
    expect(selectableAnalyticsGoals(goals).map((goal) => goal.id)).toEqual([1])
  })
})

describe('hasArchivedAnalyticsGoals', () => {
  it('アーカイブ済みの目標があればtrueを返す（トグルを表示する）', () => {
    const goals = [makeGoal(1), makeGoal(2, { archived_at: '2026-09-01T00:00:00' })]
    expect(hasArchivedAnalyticsGoals(goals)).toBe(true)
  })

  it('アーカイブ済みの目標がなければfalseを返す（トグルを表示しない）', () => {
    expect(hasArchivedAnalyticsGoals([makeGoal(1)])).toBe(false)
  })

  it('アーカイブ済みが下書きのみの場合はfalseを返す（トグルONでも増えないため）', () => {
    const goals = [makeGoal(1, { status: 'DRAFT', archived_at: '2026-09-01T00:00:00' })]
    expect(hasArchivedAnalyticsGoals(goals)).toBe(false)
  })
})
