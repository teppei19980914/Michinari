/** useDailyReportDraft の下書きマージ挙動を固定する回帰テスト。
 *
 * 2026-09-18に発生した不具合の再発防止。SC-06/SC-07を開いた状態のまま（アプリ内遷移で
 * DailyReportDraftProviderを保持したまま）教材・書籍・案件・目標を新規作成して画面に戻ると、
 * hydrateはstoreKeyごとに1回きりのため、後から増えたidの下書き値が一度も作られず
 * 実績入力欄が空のまま表示され、そのまま確定できてしまっていた（reading_logsが空のまま
 * REPORTEDになるデータロス）。本ファイルはhydrate後にクエリだけが最新化されるケースを
 * 直接再現し、新規id分がマージされること・既存の入力途中の値が上書きされないことを守る。
 *
 * DailyReportPage.test.tsx側は画面描画込みの統合的な回帰検知を担うため、本ファイルは
 * useDailyReportDraft単体の分岐（4カテゴリ×新規追加・既存保持・変化なし）を網羅する
 * 目的に絞る（CODING_RULES.md テストカバレッジ）。 */
import { describe, expect, it } from 'vitest'
import { act } from 'react'
import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { DailyReportDraftProvider } from './dailyReportDraftStore'
import { useDailyReportDraft } from './useDailyReportDraft'
import type { DailyRecordQueries } from './useDailyRecordQueries'
import { makeBook, makeGoal, makeWorkAssignment } from '../../test/fixtures'
import type { DailyRecordRead, QuotaItemRead } from '../../api/records'
import type { ActiveReadingBook, ActiveWorkAssignment, GoalRead } from '../../api/goals'

const LOGICAL_DATE = '2026-09-18'
const STORE_KEY = `daily-report:${LOGICAL_DATE}`

function fakeQuery<T>(data: T): UseQueryResult<T> {
  return { data } as unknown as UseQueryResult<T>
}

function buildRecord(overrides: Partial<DailyRecordRead> = {}): DailyRecordRead {
  return {
    record_date: LOGICAL_DATE,
    exam_record_state: null,
    reading_record_state: null,
    work_record_state: null,
    exam_reported_at: null,
    reading_reported_at: null,
    work_reported_at: null,
    diary_entries: [],
    study_logs: [],
    reading_logs: [],
    work_logs: [],
    comments: [],
    chat_messages: [],
    ...overrides,
  }
}

const EXAM_GOAL = makeGoal({ id: 1, category: 'EXAM' })
const READING_GOAL = makeGoal({ id: 8, category: 'READING' })
const WORK_GOAL = makeGoal({ id: 3, category: 'WORK' })

const BOOK = makeBook({ id: 2, goal_id: READING_GOAL.id })
const WORK_ASSIGNMENT = makeWorkAssignment({ id: 20, goal_id: WORK_GOAL.id })

const QUOTA_ITEM = {
  material_id: 30,
  material_name: 'material',
  unit_label: 'page',
  current_cycle: 1,
  planned_cycles: 3,
  daily_quota: 10,
  quality_metric_type: 'NONE',
  goal_id: EXAM_GOAL.id,
  goal_name: EXAM_GOAL.name,
  slot_defaults: [],
} as QuotaItemRead

type QueriesOverrides = {
  record?: DailyRecordRead
  quota?: QuotaItemRead[]
  readingBooks?: ActiveReadingBook[]
  workAssignments?: ActiveWorkAssignment[]
  goals?: GoalRead[]
}

function buildQueries(overrides: QueriesOverrides = {}): DailyRecordQueries {
  return {
    record: fakeQuery(overrides.record ?? buildRecord()),
    quota: fakeQuery(overrides.quota ?? []),
    readingBooks: fakeQuery(overrides.readingBooks ?? []),
    workAssignments: fakeQuery(overrides.workAssignments ?? []),
    goals: fakeQuery(overrides.goals ?? []),
  }
}

function wrapper({ children }: { children: ReactNode }) {
  return <DailyReportDraftProvider>{children}</DailyReportDraftProvider>
}

function setup(initialQueries: DailyRecordQueries) {
  return renderHook(({ queries }: { queries: DailyRecordQueries }) => useDailyReportDraft(STORE_KEY, queries), {
    wrapper,
    initialProps: { queries: initialQueries },
  })
}

describe('useDailyReportDraft（hydrate後に新規作成された項目のマージ）', () => {
  it('fills the reading log value of a book that appears only after the draft was hydrated', () => {
    const { result, rerender } = setup(buildQueries())

    // hydrate完了時点ではまだ読書目標・書籍が存在しない。
    expect(result.current.readingLogValues).toEqual({})

    // 画面を開いたまま読書目標・書籍を新規作成した状況を再現する(クエリだけ最新化)。
    act(() => {
      rerender({ queries: buildQueries({ readingBooks: [{ goal: READING_GOAL, book: BOOK }] }) })
    })

    expect(result.current.readingLogValues[BOOK.id]).toBeDefined()
    expect(result.current.readingLogValues[BOOK.id].freeText).toBe('')
  })

  it('fills the study log value of a material that appears only after the draft was hydrated', () => {
    const { result, rerender } = setup(buildQueries())

    expect(result.current.studyLogValues).toEqual({})

    act(() => {
      rerender({ queries: buildQueries({ quota: [QUOTA_ITEM] }) })
    })

    expect(result.current.studyLogValues[QUOTA_ITEM.material_id]).toBeDefined()
  })

  it('fills the work log value of an assignment that appears only after the draft was hydrated', () => {
    const { result, rerender } = setup(buildQueries())

    expect(result.current.workLogValues).toEqual({})

    act(() => {
      rerender({
        queries: buildQueries({ workAssignments: [{ goal: WORK_GOAL, workAssignment: WORK_ASSIGNMENT }] }),
      })
    })

    expect(result.current.workLogValues[WORK_ASSIGNMENT.id]).toBeDefined()
  })

  it('fills the diary value of an exam goal that appears only after the draft was hydrated', () => {
    const { result, rerender } = setup(buildQueries())

    expect(result.current.diaryValues).toEqual({})

    act(() => {
      rerender({ queries: buildQueries({ goals: [EXAM_GOAL] }) })
    })

    expect(result.current.diaryValues[EXAM_GOAL.id]).toBeDefined()
  })

  it('fills every category at once when a rerender introduces several new items together', () => {
    // 目標詳細画面を開いたまま複数カテゴリを新規作成して戻る場合もあり得るため、
    // 単一カテゴリだけでなく同時発生のケースも固定する。
    const { result, rerender } = setup(buildQueries())

    act(() => {
      rerender({
        queries: buildQueries({
          quota: [QUOTA_ITEM],
          readingBooks: [{ goal: READING_GOAL, book: BOOK }],
          workAssignments: [{ goal: WORK_GOAL, workAssignment: WORK_ASSIGNMENT }],
          goals: [EXAM_GOAL],
        }),
      })
    })

    expect(result.current.studyLogValues[QUOTA_ITEM.material_id]).toBeDefined()
    expect(result.current.readingLogValues[BOOK.id]).toBeDefined()
    expect(result.current.workLogValues[WORK_ASSIGNMENT.id]).toBeDefined()
    expect(result.current.diaryValues[EXAM_GOAL.id]).toBeDefined()
  })

  it('keeps an already-edited draft value untouched when a new book is merged in', () => {
    const { result, rerender } = setup(buildQueries({ readingBooks: [{ goal: READING_GOAL, book: BOOK }] }))

    act(() => {
      result.current.setReadingLogValues((current) => ({
        ...current,
        [BOOK.id]: { ...current[BOOK.id], freeText: 'in-progress draft' },
      }))
    })
    expect(result.current.readingLogValues[BOOK.id].freeText).toBe('in-progress draft')

    const SECOND_BOOK = makeBook({ id: 99, goal_id: READING_GOAL.id })
    act(() => {
      rerender({
        queries: buildQueries({
          readingBooks: [
            { goal: READING_GOAL, book: BOOK },
            { goal: READING_GOAL, book: SECOND_BOOK },
          ],
        }),
      })
    })

    // 新しく増えた書籍の分だけ追加され、既に入力していた内容は残る。
    expect(result.current.readingLogValues[BOOK.id].freeText).toBe('in-progress draft')
    expect(result.current.readingLogValues[SECOND_BOOK.id]).toBeDefined()
  })

  it('keeps every category reference unchanged when a rerender introduces no new ids (no-op merge)', () => {
    const { result, rerender } = setup(
      buildQueries({
        quota: [QUOTA_ITEM],
        readingBooks: [{ goal: READING_GOAL, book: BOOK }],
        workAssignments: [{ goal: WORK_GOAL, workAssignment: WORK_ASSIGNMENT }],
        goals: [EXAM_GOAL],
      }),
    )
    const valuesAfterHydrate = {
      study: result.current.studyLogValues,
      reading: result.current.readingLogValues,
      work: result.current.workLogValues,
      diary: result.current.diaryValues,
    }

    act(() => {
      rerender({
        queries: buildQueries({
          quota: [QUOTA_ITEM],
          readingBooks: [{ goal: READING_GOAL, book: BOOK }],
          workAssignments: [{ goal: WORK_GOAL, workAssignment: WORK_ASSIGNMENT }],
          goals: [EXAM_GOAL],
        }),
      })
    })

    // 同じ構成での再取得では、4カテゴリとも差分が無いためsetDraftを呼ばず参照が変わらない。
    expect(result.current.studyLogValues).toBe(valuesAfterHydrate.study)
    expect(result.current.readingLogValues).toBe(valuesAfterHydrate.reading)
    expect(result.current.workLogValues).toBe(valuesAfterHydrate.work)
    expect(result.current.diaryValues).toBe(valuesAfterHydrate.diary)
  })
})
