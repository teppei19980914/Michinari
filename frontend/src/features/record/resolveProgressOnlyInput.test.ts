import { describe, expect, it } from 'vitest'
import {
  resolveProgressOnlyInput,
  type ProgressOnlyDraftValues,
  type ProgressOnlyTargetSections,
} from './resolveProgressOnlyInput'
import type { CategoryReportedState } from './categoryCompletion'

const MATERIAL_ID = 30
const BOOK_ID = 40
const WORK_ASSIGNMENT_ID = 50

/** 3カテゴリすべてに入力があり、いずれも未確定の状態。各テストで必要な分だけ差し替える。 */
const FILLED_DRAFT: ProgressOnlyDraftValues = {
  studyLogValues: {
    [MATERIAL_ID]: { slotMinutes: {}, amountCompleted: '5', cycleNumber: '1', qualityValue: '' },
  },
  readingLogValues: {
    [BOOK_ID]: { recallBody: 'recall', slotMinutes: {}, currentPage: '' },
  },
  workLogValues: {
    [WORK_ASSIGNMENT_ID]: { body: 'work' },
  },
}

const EMPTY_DRAFT: ProgressOnlyDraftValues = {
  studyLogValues: {},
  readingLogValues: {},
  workLogValues: {},
}

const ALL_SECTIONS: ProgressOnlyTargetSections = {
  showExamSection: true,
  showReadingSection: true,
  showWorkSection: true,
}

const NOTHING_REPORTED: CategoryReportedState = {
  isExamReported: false,
  isReadingReported: false,
  isWorkReported: false,
}

function resolve(
  overrides: {
    sections?: Partial<ProgressOnlyTargetSections>
    reported?: Partial<CategoryReportedState>
    draft?: ProgressOnlyDraftValues
  } = {},
) {
  return resolveProgressOnlyInput({
    sections: { ...ALL_SECTIONS, ...overrides.sections },
    reported: { ...NOTHING_REPORTED, ...overrides.reported },
    draft: overrides.draft ?? FILLED_DRAFT,
  })
}

describe('resolveProgressOnlyInput', () => {
  describe('表示するセクション', () => {
    it('対象があり未確定のカテゴリをすべて表示する', () => {
      const input = resolve()

      expect(input.showExamSection).toBe(true)
      expect(input.showReadingSection).toBe(true)
      expect(input.showWorkSection).toBe(true)
    })

    it.each([
      ['exam', { showExamSection: false }, 'showExamSection'],
      ['reading', { showReadingSection: false }, 'showReadingSection'],
      ['work', { showWorkSection: false }, 'showWorkSection'],
    ] as const)('%s に対象が無ければ表示しない', (_name, sections, field) => {
      expect(resolve({ sections })[field]).toBe(false)
    })

    it.each([
      ['exam', { isExamReported: true }, 'showExamSection'],
      ['reading', { isReadingReported: true }, 'showReadingSection'],
      ['work', { isWorkReported: true }, 'showWorkSection'],
    ] as const)('%s が確定済みなら表示しない（変更不可。仕様書7.2）', (_name, reported, field) => {
      expect(resolve({ reported })[field]).toBe(false)
    })
  })

  describe('送信内容', () => {
    it('表示している3カテゴリの実績をまとめて送る', () => {
      const { payload } = resolve()

      expect(payload.study_logs).toEqual([
        expect.objectContaining({ material_id: MATERIAL_ID, amount_completed: 5 }),
      ])
      expect(payload.reading_logs).toEqual([
        expect.objectContaining({ book_id: BOOK_ID, recall_body: 'recall' }),
      ])
      expect(payload.work_logs).toEqual([
        expect.objectContaining({ work_assignment_id: WORK_ASSIGNMENT_ID, body: 'work' }),
      ])
    })

    // 確定済みカテゴリの下書きは既存の実績で初期化されるため、送信対象から明示的に外さないと
    // サーバに拒否され（IMMUTABLE_RECORD）、未確定カテゴリの登録まで巻き添えで失敗する。
    it('確定済みカテゴリの実績は送らない', () => {
      const { payload } = resolve({ reported: { isExamReported: true } })

      expect(payload.study_logs).toEqual([])
      expect(payload.reading_logs).toHaveLength(1)
      expect(payload.work_logs).toHaveLength(1)
    })

    it('対象の無いカテゴリの実績は送らない', () => {
      const { payload } = resolve({ sections: { showReadingSection: false } })

      expect(payload.reading_logs).toEqual([])
    })
  })

  describe('登録ボタンの可否', () => {
    it.each([
      ['study', { ...EMPTY_DRAFT, studyLogValues: FILLED_DRAFT.studyLogValues }],
      ['reading', { ...EMPTY_DRAFT, readingLogValues: FILLED_DRAFT.readingLogValues }],
      ['work', { ...EMPTY_DRAFT, workLogValues: FILLED_DRAFT.workLogValues }],
    ] as const)('%s だけでも入力があれば登録できる', (_name, draft) => {
      expect(resolve({ draft }).canRegister).toBe(true)
    })

    it('どのカテゴリにも入力が無ければ登録できない', () => {
      expect(resolve({ draft: EMPTY_DRAFT }).canRegister).toBe(false)
    })

    it('入力があっても全カテゴリが確定済みなら登録できない', () => {
      const reported = { isExamReported: true, isReadingReported: true, isWorkReported: true }
      expect(resolve({ reported }).canRegister).toBe(false)
    })
  })
})
