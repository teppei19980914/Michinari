import { describe, expect, it } from 'vitest'
import type { CalendarDayRead } from '../../api/calendar'
import type { TodayRead } from '../../api/records'
import { resolveCalendarGuard, type CalendarGuardQueries } from './resolveCalendarGuard'
import type { QueryLike } from '../../utils/queryGuard'

const TODAY: TodayRead = { logical_date: '2026-09-13', record_state: null }
const DAYS = [] as CalendarDayRead[]

function buildQuery<T>(data: T | undefined, overrides: Partial<QueryLike<T>> = {}): QueryLike<T> {
  return { isLoading: false, isError: false, error: null, data, ...overrides }
}

/** 全取得が成功した状態。各テストで必要な1本だけを差し替える。 */
function buildQueries(overrides: Partial<CalendarGuardQueries> = {}): CalendarGuardQueries {
  return {
    today: buildQuery<TodayRead>(TODAY),
    calendar: buildQuery<CalendarDayRead[]>(DAYS),
    goals: buildQuery<unknown>([]),
    ...overrides,
  }
}

function resolve(overrides: Partial<CalendarGuardQueries> = {}) {
  return resolveCalendarGuard(buildQueries(overrides))
}

const QUERY_NAMES = [
  'today',
  'calendar',
  'goals',
] as const satisfies readonly (keyof CalendarGuardQueries)[]

describe('resolveCalendarGuard', () => {
  describe('LOADING', () => {
    // 取得が1本でも進行中なら待つ。どの1本でも成立することを確認し、取得を追加した際に
    // 判定へ組み込み忘れると落ちるようにする。
    it.each(QUERY_NAMES)('waits while the %s query is loading', (name) => {
      expect(resolve({ [name]: buildQuery(undefined, { isLoading: true }) }).kind).toBe('LOADING')
    })
  })

  describe('ERROR', () => {
    it.each(QUERY_NAMES)('reports an error when the %s query fails', (name) => {
      const error = new Error(name)
      expect(resolve({ [name]: buildQuery(undefined, { isError: true, error }) })).toEqual({
        kind: 'ERROR',
        error,
      })
    })

    it('prefers the error of the query listed first', () => {
      const todayError = new Error('today')
      const calendarError = new Error('calendar')
      const guard = resolve({
        today: buildQuery<TodayRead>(undefined, { isError: true, error: todayError }),
        calendar: buildQuery<CalendarDayRead[]>(undefined, { isError: true, error: calendarError }),
      })
      expect(guard).toEqual({ kind: 'ERROR', error: todayError })
    })

    // 取得は成功扱いなのにデータが無い場合も描画できない。この2本のみデータの存在まで要求する。
    it.each(['today', 'calendar'] as const)(
      'reports an error when the %s query has no data',
      (name) => {
        expect(resolve({ [name]: buildQuery(undefined) })).toEqual({
          kind: 'ERROR',
          error: undefined,
        })
      },
    )
  })

  describe('READY', () => {
    it('returns the fetched today and days so the caller needs no non-null assertion', () => {
      expect(resolve()).toEqual({ kind: 'READY', today: TODAY, days: DAYS })
    })

    // goalsは補助表示（受験日等）にしか使わない。目標が0件の場合と同じ表示になれば足りるため、
    // データが無くてもカレンダー本体は表示する。
    it('stays ready when the goal query returned no data', () => {
      expect(resolve({ goals: buildQuery(undefined) }).kind).toBe('READY')
    })
  })
})
