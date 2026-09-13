import { describe, expect, it } from 'vitest'
import type { DashboardRead } from '../../api/dashboard'
import { resolveDashboardGuard, type DashboardGuardQueries } from './resolveDashboardGuard'
import type { QueryLike } from '../../utils/queryGuard'

const DASHBOARD = {
  goal_cards: [],
  goal_stats: [],
  today_quota: [],
} as unknown as DashboardRead

function buildQuery<T>(data: T | undefined, overrides: Partial<QueryLike<T>> = {}): QueryLike<T> {
  return { isLoading: false, isError: false, error: null, data, ...overrides }
}

/** 全取得が成功した状態。各テストで必要な1本だけを差し替える。 */
function buildQueries(overrides: Partial<DashboardGuardQueries> = {}): DashboardGuardQueries {
  return {
    dashboard: buildQuery<DashboardRead>(DASHBOARD),
    goals: buildQuery<unknown>([]),
    ...overrides,
  }
}

function resolve(overrides: Partial<DashboardGuardQueries> = {}) {
  return resolveDashboardGuard(buildQueries(overrides))
}

const QUERY_NAMES = [
  'dashboard',
  'goals',
] as const satisfies readonly (keyof DashboardGuardQueries)[]

describe('resolveDashboardGuard', () => {
  describe('LOADING', () => {
    // 取得が1本でも進行中なら待つ。どの1本でも成立することを確認し、取得を追加した際に
    // 判定へ組み込み忘れると落ちるようにする。
    it.each(QUERY_NAMES)('waits while the %s query is loading', (name) => {
      expect(resolve({ [name]: buildQuery(undefined, { isLoading: true }) }).kind).toBe('LOADING')
    })
  })

  describe('ERROR', () => {
    // 目標一覧だけが失敗した場合も空の画面ではなくエラーを出す（全セクションが
    // 空表示になるのを避けるため。DashboardPage.test.tsxの描画テストと対の判定）。
    it.each(QUERY_NAMES)('reports an error when the %s query fails', (name) => {
      const error = new Error(name)
      expect(resolve({ [name]: buildQuery(undefined, { isError: true, error }) })).toEqual({
        kind: 'ERROR',
        error,
      })
    })

    it('prefers the error of the query listed first', () => {
      const dashboardError = new Error('dashboard')
      const goalsError = new Error('goals')
      const guard = resolve({
        dashboard: buildQuery<DashboardRead>(undefined, { isError: true, error: dashboardError }),
        goals: buildQuery<unknown>(undefined, { isError: true, error: goalsError }),
      })
      expect(guard).toEqual({ kind: 'ERROR', error: dashboardError })
    })

    // 取得は成功扱いなのにデータが無い場合も描画できない。dashboardのみ存在まで要求する。
    it('reports an error when the dashboard query has no data', () => {
      expect(resolve({ dashboard: buildQuery<DashboardRead>(undefined) })).toEqual({
        kind: 'ERROR',
        error: undefined,
      })
    })
  })

  describe('READY', () => {
    it('returns the fetched dashboard so the caller needs no non-null assertion', () => {
      expect(resolve()).toEqual({ kind: 'READY', dashboard: DASHBOARD })
    })

    // goalsは目標タブの組み立てにしか使わない。目標が0件の場合と同じ表示になれば足りるため、
    // データが無くてもダッシュボード本体は表示する。
    it('stays ready when the goal query returned no data', () => {
      expect(resolve({ goals: buildQuery(undefined) }).kind).toBe('READY')
    })
  })
})
