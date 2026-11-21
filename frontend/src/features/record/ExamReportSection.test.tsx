/** ExamReportSectionが、確定済みサマリ内で「今日の記録に出てきた用語」カード
 * （開発Todo_単語帳_v1.0 要件D）を日記（学んだこと）のある目標ごとに表示することを守る。
 * カード自体の挙動（提案の取得・採用・見送り）はTodayVocabSuggestionsCard.test.tsxが守る。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { DailyRecordRead } from '../../api/records'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'
import type { CategoryActions } from './useDailyReportActions'
import { ExamReportSection, type ExamReportSectionProps } from './ExamReportSection'

const getAiStatus = vi.hoisted(() => vi.fn())
vi.mock('../../api/ai', () => ({ getAiStatus }))

const getVocabDecks = vi.hoisted(() => vi.fn())
const getVocabTermSuggestions = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({ getVocabDecks, getVocabTermSuggestions }))

const EXAM_GOAL_ID = 1

function buildRecord(overrides: Partial<DailyRecordRead> = {}): DailyRecordRead {
  return {
    record_date: '2026-09-13',
    exam_record_state: 'REPORTED',
    exam_reported_at: '2026-09-13T00:00:00Z',
    reading_record_state: null,
    reading_reported_at: null,
    work_record_state: null,
    work_reported_at: null,
    exam_mood: null,
    reading_mood: null,
    work_mood: null,
    diary_entries: [],
    study_logs: [],
    reading_logs: [],
    work_logs: [],
    comments: [],
    chat_messages: [],
    ...overrides,
  }
}

function buildDraft(): DailyReportDraft {
  return {
    studyLogValues: {},
    setStudyLogValues: vi.fn(),
    readingLogValues: {},
    setReadingLogValues: vi.fn(),
    workLogValues: {},
    setWorkLogValues: vi.fn(),
    diaryValues: {},
    setDiaryValues: vi.fn(),
    chatMessages: [],
    setChatMessages: vi.fn(),
    hasUnsavedInput: false,
    examMood: null,
    setExamMood: vi.fn(),
    readingMood: null,
    setReadingMood: vi.fn(),
    workMood: null,
    setWorkMood: vi.fn(),
    examMode: 'NORMAL',
    setExamMode: vi.fn(),
    readingMode: 'NORMAL',
    setReadingMode: vi.fn(),
    workMode: 'NORMAL',
    setWorkMode: vi.fn(),
  }
}

function buildTargets(): VisibleReportTargets {
  return {
    presence: { hasExamCategory: true, hasReadingCategory: false, hasWorkCategory: false },
    quotaItems: [],
    diaryGoals: [],
    books: [],
    workAssignments: [],
    showExamSection: true,
    showReadingSection: false,
    showWorkSection: false,
  }
}

function buildActions(): CategoryActions {
  return {
    chat: { isPending: false, wasTruncated: false, contextCategories: [], send: vi.fn() },
    finalize: { isPending: false, submit: vi.fn() },
    messages: [],
  }
}

function renderSection(overrides: Partial<ExamReportSectionProps> = {}) {
  renderWithProviders(
    <ExamReportSection
      targetDate="2026-09-13"
      record={buildRecord()}
      quotaItems={[]}
      targets={buildTargets()}
      draft={buildDraft()}
      slotNames={new Map()}
      actions={buildActions()}
      isReported
      quickNoteMaxChars={200}
      {...overrides}
    />,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getAiStatus.mockResolvedValue({
    authenticated: true,
    model_status: {},
    login_in_progress: false,
  })
  getVocabDecks.mockResolvedValue([])
  getVocabTermSuggestions.mockResolvedValue({ suggestions: [], default_deck_id: null })
})

afterEach(() => {
  cleanup()
})

describe('ExamReportSectionの用語提案カード', () => {
  it('does not request vocab decks when no diary entry has learned text', () => {
    renderSection({ record: buildRecord({ diary_entries: [] }) })

    expect(getVocabDecks).not.toHaveBeenCalled()
  })

  it('skips entries without a goal id or with blank learned text', () => {
    renderSection({
      record: buildRecord({
        diary_entries: [
          { goal_id: null, goal_name: null, diary_body: '', diary_learned: 'x' },
          {
            goal_id: EXAM_GOAL_ID,
            goal_name: 'exam-goal',
            diary_body: '',
            diary_learned: '   ',
          },
        ],
      }),
    })

    expect(getVocabDecks).not.toHaveBeenCalled()
  })

  it('requests vocab decks for a goal whose diary has learned text', async () => {
    renderSection({
      record: buildRecord({
        diary_entries: [
          {
            goal_id: EXAM_GOAL_ID,
            goal_name: 'exam-goal',
            diary_body: '',
            diary_learned: 'TCPを学んだ',
          },
        ],
      }),
    })

    await waitFor(() => expect(getVocabDecks).toHaveBeenCalledWith(EXAM_GOAL_ID))
    expect(await screen.findByText(t('vocab.suggestions.noDeckNotice'))).toBeTruthy()
  })
})
