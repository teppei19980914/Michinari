import { describe, expect, it } from 'vitest'
import type { DailyRecordRead, QuotaItemRead, TodayRead } from '../../api/records'
import { resolveProgressOnlyGuard, type ProgressOnlyGuardQueries } from './resolveProgressOnlyGuard'
import type { QueryLike } from '../../utils/queryGuard'

const LOGICAL_DATE = '2026-09-13'
/** 論理的な本日より後の日（実績登録不可。仕様書7.2）。 */
const FUTURE_DATE = '2026-09-14'

const RECORD = { exam_record_state: null } as unknown as DailyRecordRead
const QUOTA = [] as QuotaItemRead[]
const TODAY: TodayRead = { logical_date: LOGICAL_DATE, record_state: null }

function buildQuery<T>(data: T | undefined, overrides: Partial<QueryLike<T>> = {}): QueryLike<T> {
  return { isLoading: false, isError: false, error: null, data, ...overrides }
}

/** 全取得が成功した状態。各テストで必要な1本だけを差し替える。 */
function buildQueries(overrides: Partial<ProgressOnlyGuardQueries> = {}): ProgressOnlyGuardQueries {
  return {
    record: buildQuery<DailyRecordRead>(RECORD),
    quota: buildQuery<QuotaItemRead[]>(QUOTA),
    today: buildQuery<TodayRead>(TODAY),
    ...overrides,
  }
}

function resolve(
  overrides: Partial<ProgressOnlyGuardQueries> = {},
  targetDate: string = LOGICAL_DATE,
) {
  return resolveProgressOnlyGuard(buildQueries(overrides), targetDate)
}

const QUERY_NAMES = [
  'record',
  'quota',
  'today',
] as const satisfies readonly (keyof ProgressOnlyGuardQueries)[]

describe('resolveProgressOnlyGuard', () => {
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
      const guard = resolve({ [name]: buildQuery(undefined, { isError: true, error }) })
      expect(guard).toEqual({ kind: 'ERROR', error })
    })

    it('prefers the error of the query listed first', () => {
      const recordError = new Error('record')
      const quotaError = new Error('quota')
      const guard = resolve({
        record: buildQuery<DailyRecordRead>(undefined, { isError: true, error: recordError }),
        quota: buildQuery<QuotaItemRead[]>(undefined, { isError: true, error: quotaError }),
      })
      expect(guard).toEqual({ kind: 'ERROR', error: recordError })
    })

    // 取得は成功扱いなのにデータが無い場合も描画できない。3本すべてが対象。
    it.each(QUERY_NAMES)('reports an error when the %s query has no data', (name) => {
      expect(resolve({ [name]: buildQuery(undefined) })).toEqual({ kind: 'ERROR', error: undefined })
    })
  })

  describe('REDIRECT_VIEW', () => {
    it('redirects when the target date is still in the future', () => {
      expect(resolve({}, FUTURE_DATE).kind).toBe('REDIRECT_VIEW')
    })

    it('redirects when the exam category is already reported', () => {
      const record = { exam_record_state: 'REPORTED' } as DailyRecordRead
      expect(resolve({ record: buildQuery(record) }).kind).toBe('REDIRECT_VIEW')
    })
  })

  describe('EDITABLE', () => {
    it('returns the fetched quota so the caller needs no non-null assertion', () => {
      expect(resolve()).toEqual({ kind: 'EDITABLE', quota: QUOTA })
    })

    // 進捗のみ登録は当日・それ以前なら日付の古さを問わない（日次報告と違い確定を伴わないため）。
    it('stays editable for a past date', () => {
      expect(resolve({}, '2026-01-01').kind).toBe('EDITABLE')
    })

    it('stays editable while only another category is reported', () => {
      const record = { exam_record_state: null, work_record_state: 'REPORTED' } as DailyRecordRead
      expect(resolve({ record: buildQuery(record) }).kind).toBe('EDITABLE')
    })
  })
})
