import { describe, expect, it } from 'vitest'
import type { DailyRecordRead } from '../../api/records'
import {
  resolveDailyReportViewGuard,
  type DailyReportViewGuardQueries,
} from './resolveDailyReportViewGuard'
import type { QueryLike } from '../../utils/queryGuard'

const RECORD = { record_date: '2026-09-13' } as unknown as DailyRecordRead

function buildQuery<T>(data: T | undefined, overrides: Partial<QueryLike<T>> = {}): QueryLike<T> {
  return { isLoading: false, isError: false, error: null, data, ...overrides }
}

/** 全取得が成功した状態。各テストで必要な1本だけを差し替える。 */
function buildQueries(
  overrides: Partial<DailyReportViewGuardQueries> = {},
): DailyReportViewGuardQueries {
  return {
    record: buildQuery<DailyRecordRead>(RECORD),
    quota: buildQuery<unknown>([]),
    readingBooks: buildQuery<unknown>([]),
    workAssignments: buildQuery<unknown>([]),
    goals: buildQuery<unknown>([]),
    ...overrides,
  }
}

function resolve(overrides: Partial<DailyReportViewGuardQueries> = {}) {
  return resolveDailyReportViewGuard(buildQueries(overrides))
}

const QUERY_NAMES = [
  'record',
  'quota',
  'readingBooks',
  'workAssignments',
  'goals',
] as const satisfies readonly (keyof DailyReportViewGuardQueries)[]

/** 記録以外の取得。失敗してもエラー画面にはしないが、完了は待つ。 */
const LABEL_QUERY_NAMES = ['quota', 'readingBooks', 'workAssignments', 'goals'] as const

describe('resolveDailyReportViewGuard', () => {
  describe('LOADING', () => {
    // 取得が1本でも進行中なら待つ。表示名（教材名等）が後から差し替わるのを避けるため、
    // 記録以外の4本も待つ対象に含まれる。
    it.each(QUERY_NAMES)('waits while the %s query is loading', (name) => {
      expect(resolve({ [name]: buildQuery(undefined, { isLoading: true }) }).kind).toBe('LOADING')
    })
  })

  describe('ERROR', () => {
    it('reports an error when the record itself cannot be read', () => {
      const error = new Error('record')
      const guard = resolve({
        record: buildQuery<DailyRecordRead>(undefined, { isError: true, error }),
      })
      expect(guard).toEqual({ kind: 'ERROR', error })
    })

    it('reports an error when the record query has no data', () => {
      expect(resolve({ record: buildQuery<DailyRecordRead>(undefined) })).toEqual({
        kind: 'ERROR',
        error: null,
      })
    })
  })

  describe('READY', () => {
    it('returns the fetched record so the caller needs no non-null assertion', () => {
      expect(resolve()).toEqual({ kind: 'READY', record: RECORD })
    })

    // 記録以外の4本は表示名を与えるためだけに使う。失敗しても記録そのものは読めるため、
    // エラー画面にはせず表示名のない状態で描画する（従来の挙動）。
    it.each(LABEL_QUERY_NAMES)('stays ready when the %s query failed', (name) => {
      const guard = resolve({ [name]: buildQuery(undefined, { isError: true, error: new Error() }) })
      expect(guard.kind).toBe('READY')
    })

    it.each(LABEL_QUERY_NAMES)('stays ready when the %s query returned no data', (name) => {
      expect(resolve({ [name]: buildQuery(undefined) }).kind).toBe('READY')
    })
  })
})
