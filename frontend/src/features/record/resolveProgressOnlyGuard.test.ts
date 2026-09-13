import { describe, expect, it } from 'vitest'
import type { DailyRecordRead, QuotaItemRead, TodayRead } from '../../api/records'
import { resolveProgressOnlyGuard, type ProgressOnlyGuardQueries } from './resolveProgressOnlyGuard'
import type { CategoryPresence } from './categoryCompletion'
import type { QueryLike } from '../../utils/queryGuard'

const LOGICAL_DATE = '2026-09-13'
/** 論理的な本日より後の日（実績登録不可。仕様書7.2）。 */
const FUTURE_DATE = '2026-09-14'

const RECORD = { exam_record_state: null } as unknown as DailyRecordRead
const QUOTA = [] as QuotaItemRead[]
const TODAY: TodayRead = { logical_date: LOGICAL_DATE, record_state: null }

/** 資格試験の目標だけが着手中（従来のEXAM専用実装と同じ前提）。 */
const EXAM_ONLY_PRESENCE: CategoryPresence = {
  hasExamCategory: true,
  hasReadingCategory: false,
  hasWorkCategory: false,
}

function buildQuery<T>(data: T | undefined, overrides: Partial<QueryLike<T>> = {}): QueryLike<T> {
  return { isLoading: false, isError: false, error: null, data, ...overrides }
}

/** 全取得が成功した状態。各テストで必要な1本だけを差し替える。 */
function buildQueries(overrides: Partial<ProgressOnlyGuardQueries> = {}): ProgressOnlyGuardQueries {
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
  overrides: Partial<ProgressOnlyGuardQueries> = {},
  targetDate: string = LOGICAL_DATE,
  presence: CategoryPresence = EXAM_ONLY_PRESENCE,
) {
  return resolveProgressOnlyGuard(buildQueries(overrides), presence, targetDate)
}

const QUERY_NAMES = [
  'record',
  'quota',
  'readingBooks',
  'workAssignments',
  'goals',
  'today',
] as const satisfies readonly (keyof ProgressOnlyGuardQueries)[]

/** データの有無まで要求する取得。readingBooks・workAssignmentsは`?? []`として扱うため含めない
 * （resolveDailyReportGuardと同じ扱い）。 */
const REQUIRED_DATA_QUERY_NAMES = [
  'record',
  'quota',
  'goals',
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

    // 取得は成功扱いなのにデータが無い場合も描画できない。
    it.each(REQUIRED_DATA_QUERY_NAMES)('reports an error when the %s query has no data', (name) => {
      expect(resolve({ [name]: buildQuery(undefined) })).toEqual({ kind: 'ERROR', error: undefined })
    })

    // 書籍・案件は取得できなくても他カテゴリの入力を妨げない（`?? []`として扱う）。
    it.each(['readingBooks', 'workAssignments'] as const)(
      'stays editable when the %s query has no data',
      (name) => {
        expect(resolve({ [name]: buildQuery(undefined) }).kind).toBe('EDITABLE')
      },
    )
  })

  describe('REDIRECT_VIEW', () => {
    it('redirects when the target date is still in the future', () => {
      expect(resolve({}, FUTURE_DATE).kind).toBe('REDIRECT_VIEW')
    })

    it('redirects when the only category in progress is already reported', () => {
      const record = { exam_record_state: 'REPORTED' } as DailyRecordRead
      expect(resolve({ record: buildQuery(record) }).kind).toBe('REDIRECT_VIEW')
    })

    it('redirects once every category in progress has been reported', () => {
      const record = {
        exam_record_state: 'REPORTED',
        reading_record_state: 'REPORTED',
        work_record_state: 'REPORTED',
      } as DailyRecordRead
      const presence: CategoryPresence = {
        hasExamCategory: true,
        hasReadingCategory: true,
        hasWorkCategory: true,
      }
      expect(resolve({ record: buildQuery(record) }, LOGICAL_DATE, presence).kind).toBe(
        'REDIRECT_VIEW',
      )
    })
  })

  describe('EDITABLE', () => {
    it('returns the fetched record and quota so the caller needs no non-null assertion', () => {
      expect(resolve()).toEqual({ kind: 'EDITABLE', record: RECORD, quota: QUOTA })
    })

    // 進捗のみ登録は当日・それ以前なら日付の古さを問わない（日次報告と違い確定を伴わないため）。
    it('stays editable for a past date', () => {
      expect(resolve({}, '2026-01-01').kind).toBe('EDITABLE')
    })

    // 2026-09-12に日次報告で是正した不具合と同型の退行を防ぐ。資格勉強を確定した日でも、
    // 読書・仕事が未確定なら進捗を登録できなければならない。
    it('stays editable while another category in progress is not reported yet', () => {
      const record = {
        exam_record_state: 'REPORTED',
        reading_record_state: null,
      } as DailyRecordRead
      const presence: CategoryPresence = {
        hasExamCategory: true,
        hasReadingCategory: true,
        hasWorkCategory: false,
      }
      expect(resolve({ record: buildQuery(record) }, LOGICAL_DATE, presence).kind).toBe('EDITABLE')
    })

    // 着手中の目標が1件も無い日は「全カテゴリ確定済み」に当たらない（isAllCategoriesReported）。
    // 入力欄の無い画面になるが、日次報告（SC-06）と同じ扱いに揃える。
    it('stays editable when no category is in progress at all', () => {
      const presence: CategoryPresence = {
        hasExamCategory: false,
        hasReadingCategory: false,
        hasWorkCategory: false,
      }
      expect(resolve({}, LOGICAL_DATE, presence).kind).toBe('EDITABLE')
    })
  })
})
