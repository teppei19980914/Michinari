import { describe, expect, it } from 'vitest'
import { t } from '../../locales/t'
import type { components } from '../../types/api.d.ts'
import { GOAL_CATEGORIES } from '../../constants/goalCategories'
import {
  canGenerateRetrospective,
  goalStatusLabelKey,
  hasOperation,
  isClosedGoalStatus,
  isDefaultListedGoal,
  resolveGoalListTarget,
} from './goalStatus'

describe('canGenerateRetrospective（総括・読了レポートは完了した目標のみ）', () => {
  it('allows generation only for a completed goal', () => {
    expect(canGenerateRetrospective('CLOSED_WITH_RESULT')).toBe(true)
  })

  it.each(['DRAFT', 'ACTIVE', 'PAUSED', 'CLOSED_WITHOUT_RESULT'] as const)(
    'refuses generation for %s',
    (status) => {
      expect(canGenerateRetrospective(status)).toBe(false)
    },
  )
})

type GoalOperation = components['schemas']['GoalOperation']

describe('isClosedGoalStatus', () => {
  it('returns false for DRAFT/ACTIVE/PAUSED', () => {
    expect(isClosedGoalStatus('DRAFT')).toBe(false)
    expect(isClosedGoalStatus('ACTIVE')).toBe(false)
    expect(isClosedGoalStatus('PAUSED')).toBe(false)
  })

  it('returns true for both closed statuses', () => {
    expect(isClosedGoalStatus('CLOSED_WITH_RESULT')).toBe(true)
    expect(isClosedGoalStatus('CLOSED_WITHOUT_RESULT')).toBe(true)
  })
})

describe('resolveGoalListTarget', () => {
  it('routes to the goal detail screen when not closed', () => {
    expect(resolveGoalListTarget(1, 'ACTIVE')).toBe('/goals/1')
  })

  it('routes to the export placeholder when closed', () => {
    expect(resolveGoalListTarget(1, 'CLOSED_WITH_RESULT')).toBe('/goals/1/export')
    expect(resolveGoalListTarget(1, 'CLOSED_WITHOUT_RESULT')).toBe('/goals/1/export')
  })
})

describe('isDefaultListedGoal（開発Todo 1-9：既定表示は下書き・実行中・一時停止）', () => {
  it('lists DRAFT/ACTIVE/PAUSED goals that are not archived', () => {
    expect(isDefaultListedGoal({ status: 'DRAFT', archived_at: null })).toBe(true)
    expect(isDefaultListedGoal({ status: 'ACTIVE', archived_at: null })).toBe(true)
    expect(isDefaultListedGoal({ status: 'PAUSED', archived_at: null })).toBe(true)
  })

  it('hides completed and interrupted goals by default', () => {
    expect(isDefaultListedGoal({ status: 'CLOSED_WITH_RESULT', archived_at: null })).toBe(false)
    expect(isDefaultListedGoal({ status: 'CLOSED_WITHOUT_RESULT', archived_at: null })).toBe(false)
  })

  it('hides archived goals by default, whatever their status', () => {
    expect(isDefaultListedGoal({ status: 'ACTIVE', archived_at: '2026-08-30T00:00:00' })).toBe(false)
  })
})

describe('hasOperation（操作の可否はサーバーの available_operations に従う）', () => {
  it('reports whether the server offered an operation', () => {
    const goal = { available_operations: ['PAUSE', 'COMPLETE', 'ABANDON'] as GoalOperation[] }
    expect(hasOperation(goal, 'PAUSE')).toBe(true)
    expect(hasOperation(goal, 'RESUME')).toBe(false)
  })
})

describe('goalStatusLabelKey（状態の表示名は種別ごとに分かれる）', () => {
  it('resolves every category and status to an actual locale entry', () => {
    for (const category of GOAL_CATEGORIES) {
      for (const status of [
        'DRAFT',
        'ACTIVE',
        'PAUSED',
        'CLOSED_WITH_RESULT',
        'CLOSED_WITHOUT_RESULT',
      ] as const) {
        const key = goalStatusLabelKey(category, status)
        expect(t(key), `未登録のロケールキー: ${key}`).not.toBe(key)
      }
    }
  })

  it('uses the reading wording for a completed reading goal', () => {
    expect(t(goalStatusLabelKey('READING', 'CLOSED_WITH_RESULT'))).toBe('読了')
    expect(t(goalStatusLabelKey('WORK', 'CLOSED_WITHOUT_RESULT'))).toBe('中止・打ち切り')
  })
})
