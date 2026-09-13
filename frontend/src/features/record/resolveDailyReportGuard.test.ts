import { describe, expect, it } from 'vitest'
import type { DailyRecordRead, QuotaItemRead, TodayRead } from '../../api/records'
import {
  resolveDailyReportGuard,
  type DailyReportGuardQueries,
  type QueryLike,
} from './resolveDailyReportGuard'
import type { CategoryPresence } from './categoryCompletion'

const LOGICAL_DATE = '2026-09-13'
/** 当日・前日のいずれでもない日（入力可能期間外。仕様書7.2）。 */
const OUT_OF_RANGE_DATE = '2026-09-10'

const RECORD = {
  record_date: LOGICAL_DATE,
  exam_record_state: null,
  reading_record_state: null,
  work_record_state: null,
} as unknown as DailyRecordRead

const QUOTA = [] as QuotaItemRead[]
const TODAY: TodayRead = { logical_date: LOGICAL_DATE, record_state: null }

const EXAM_ONLY: CategoryPresence = {
  hasExamCategory: true,
  hasReadingCategory: false,
  hasWorkCategory: false,
}

function buildQuery<T>(data: T | undefined, overrides: Partial<QueryLike<T>> = {}): QueryLike<T> {
  return { isLoading: false, isError: false, error: null, data, ...overrides }
}

/** 全取得が成功した状態。各テストで必要な1本だけを差し替える。 */
function buildQueries(overrides: Partial<DailyReportGuardQueries> = {}): DailyReportGuardQueries {
  return {
    record: buildQuery<DailyRecordRead>(RECORD),
    quota: buildQuery<QuotaItemRead[]>(QUOTA),
    readingBooks: buildQuery<unknown>([]),
    workAssignments: buildQuery<unknown>([]),
    goals: buildQuery<unknown>([]),
    today: buildQuery<TodayRead>(TODAY),
    ...overrides,
  }
}

function resolve(
  overrides: Partial<DailyReportGuardQueries> = {},
  presence: CategoryPresence = EXAM_ONLY,
  targetDate: string = LOGICAL_DATE,
) {
  return resolveDailyReportGuard(buildQueries(overrides), presence, targetDate)
}

const QUERY_NAMES = [
  'record',
  'quota',
  'readingBooks',
  'workAssignments',
  'goals',
  'today',
] as const satisfies readonly (keyof DailyReportGuardQueries)[]

describe('resolveDailyReportGuard', () => {
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

    // 取得は成功扱いなのにデータが無い場合も描画できない。この4本のみデータの存在まで要求する。
    it.each(['record', 'quota', 'goals', 'today'] as const)(
      'reports an error when the %s query has no data',
      (name) => {
        const guard = resolve({ [name]: buildQuery(undefined) })
        expect(guard).toEqual({ kind: 'ERROR', error: undefined })
      },
    )
  })

  describe('REDIRECT_VIEW', () => {
    it('redirects when the target date is outside the input window', () => {
      expect(resolve({}, EXAM_ONLY, OUT_OF_RANGE_DATE).kind).toBe('REDIRECT_VIEW')
    })

    it('redirects when every started category is already reported', () => {
      const record = { ...RECORD, exam_record_state: 'REPORTED' } as DailyRecordRead
      expect(resolve({ record: buildQuery(record) }).kind).toBe('REDIRECT_VIEW')
    })
  })

  describe('EDITABLE', () => {
    it('returns the fetched record and quota so the caller needs no non-null assertion', () => {
      expect(resolve()).toEqual({ kind: 'EDITABLE', record: RECORD, quota: QUOTA })
    })

    it('stays editable when only some categories are reported', () => {
      // 1カテゴリ確定しても他カテゴリは入力・確定できる（仕様書1.1（改20））。
      const record = { ...RECORD, exam_record_state: 'REPORTED' } as DailyRecordRead
      const presence: CategoryPresence = {
        hasExamCategory: true,
        hasReadingCategory: true,
        hasWorkCategory: false,
      }
      expect(resolve({ record: buildQuery(record) }, presence).kind).toBe('EDITABLE')
    })

    it.each(['readingBooks', 'workAssignments'] as const)(
      'stays editable when the %s query returned no data (it is treated as an empty list)',
      (name) => {
        expect(resolve({ [name]: buildQuery(undefined) }).kind).toBe('EDITABLE')
      },
    )
  })
})
