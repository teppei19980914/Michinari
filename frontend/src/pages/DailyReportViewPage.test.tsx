/** SC-08 日次報告閲覧（DailyReportViewPage）のセクション表示規則を固定する回帰テスト。
 *
 * 入力画面（SC-06）と閲覧画面（SC-08）で表示条件がずれると、同じ日の記録が画面によって
 * 違って見える。共通の判定（features/record/sectionVisibility.ts）へ寄せるにあたり、
 * この画面の従来の見え方を先に固定しておく。
 *
 * カバレッジの扱いは DailyReportPage.test.tsx と同じ（vite.config.ts の coverage.exclude）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { ROUTES, ROUTE_PATTERNS } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { t } from '../locales/t'
import * as goalsApi from '../api/goals'
import * as recordsApi from '../api/records'
import type { BookRead, GoalRead, WorkAssignmentRead } from '../api/goals'
import type { DailyRecordRead, QuotaItemRead } from '../api/records'
import { DailyReportViewPage } from './DailyReportViewPage'

vi.mock('../api/goals')
vi.mock('../api/records')

const TARGET_DATE = '2026-09-13'
const EXAM_GOAL_NAME = 'exam-goal'
const READING_GOAL_NAME = 'reading-goal'
const WORK_GOAL_NAME = 'work-goal'

function buildGoal(id: number, category: GoalRead['category'], name: string): GoalRead {
  return {
    id,
    category,
    name,
    start_date: TARGET_DATE,
    status: 'ACTIVE',
    memo: null,
    activated_at: null,
    closed_at: null,
    archived_at: null,
  }
}

const EXAM_GOAL = buildGoal(1, 'EXAM', EXAM_GOAL_NAME)
const READING_GOAL = buildGoal(2, 'READING', READING_GOAL_NAME)
const WORK_GOAL = buildGoal(3, 'WORK', WORK_GOAL_NAME)

const BOOK = { id: 10, goal_id: READING_GOAL.id, title: 'book-title', total_pages: 200 } as BookRead
const WORK_ASSIGNMENT = {
  id: 20,
  goal_id: WORK_GOAL.id,
  client_name: 'client-name',
} as WorkAssignmentRead

const QUOTA_ITEM = {
  material_id: 30,
  material_name: 'material',
  unit_label: 'page',
  quality_metric_type: 'NONE',
  goal_id: EXAM_GOAL.id,
  goal_name: EXAM_GOAL_NAME,
  slot_defaults: [],
} as unknown as QuotaItemRead

function buildRecord(overrides: Partial<DailyRecordRead> = {}): DailyRecordRead {
  return {
    record_date: TARGET_DATE,
    exam_record_state: 'REPORTED',
    reading_record_state: 'REPORTED',
    work_record_state: 'REPORTED',
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

const READING_LOG = {
  id: 40,
  book_id: BOOK.id,
  recall_body: 'recall-body',
  minutes_spent: null,
  slot_minutes: [],
  current_page: null,
}
const WORK_LOG = { id: 50, work_assignment_id: WORK_ASSIGNMENT.id, body: 'work-body' }

/** 3カテゴリすべてに記録がある日。着手中の目標も3件のため目標タブが表示される。 */
function buildFullRecord(): DailyRecordRead {
  return buildRecord({
    reading_logs: [READING_LOG],
    work_logs: [WORK_LOG],
    diary_entries: [
      { goal_id: EXAM_GOAL.id, goal_name: EXAM_GOAL_NAME, diary_body: 'diary-body', diary_learned: null },
    ],
  })
}

function setupQueries(goals: GoalRead[], record: DailyRecordRead) {
  vi.mocked(goalsApi.listGoals).mockResolvedValue(goals)
  vi.mocked(goalsApi.listActiveReadingBooks).mockResolvedValue(
    goals.some((goal) => goal.category === 'READING') ? [{ goal: READING_GOAL, book: BOOK }] : [],
  )
  vi.mocked(goalsApi.listActiveWorkAssignments).mockResolvedValue(
    goals.some((goal) => goal.category === 'WORK')
      ? [{ goal: WORK_GOAL, workAssignment: WORK_ASSIGNMENT }]
      : [],
  )
  vi.mocked(recordsApi.getRecord).mockResolvedValue(record)
  vi.mocked(recordsApi.getQuota).mockResolvedValue([QUOTA_ITEM])
}

function renderPage() {
  renderWithProviders(
    <Routes>
      <Route path={ROUTE_PATTERNS.dailyReportView} element={<DailyReportViewPage />} />
    </Routes>,
    { initialEntries: [ROUTES.dailyReportView(TARGET_DATE)] },
  )
}

function getGoalTab(goalName: string) {
  return screen.getByRole('button', { name: new RegExp(goalName) })
}

async function waitForTitle() {
  await screen.findByText(t('dailyReportView.title', { date: TARGET_DATE }))
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('DailyReportViewPage', () => {
  it('shows every category at once when there is no goal tab bar', async () => {
    // 着手中の目標が1件のみ＝タブ非表示。この場合は記録の有無だけで表示を決める。
    setupQueries([EXAM_GOAL], buildRecord({ reading_logs: [READING_LOG], work_logs: [WORK_LOG] }))
    renderPage()
    await waitForTitle()

    expect(screen.getByText(t('dailyReportView.studyLog.title'))).toBeTruthy()
    expect(screen.getByText(t('dailyReportView.readingLog.title'))).toBeTruthy()
    expect(screen.getByText(t('dailyReportView.workLog.title'))).toBeTruthy()
  })

  it('hides the categories that have no record when there is no goal tab bar', async () => {
    setupQueries([EXAM_GOAL], buildRecord())
    renderPage()
    await waitForTitle()

    // 資格試験のセクションはタブが無い限り常に表示する（従来の挙動）。
    expect(screen.getByText(t('dailyReportView.studyLog.title'))).toBeTruthy()
    expect(screen.queryByText(t('dailyReportView.readingLog.title'))).toBe(null)
    expect(screen.queryByText(t('dailyReportView.workLog.title'))).toBe(null)
  })

  it('narrows the visible section to the selected tab', async () => {
    const user = userEvent.setup()
    setupQueries([EXAM_GOAL, READING_GOAL, WORK_GOAL], buildFullRecord())
    renderPage()
    await waitForTitle()

    // 初期選択は最初のACTIVE目標（資格試験）。
    expect(screen.getByText(t('dailyReportView.studyLog.title'))).toBeTruthy()
    expect(screen.queryByText(t('dailyReportView.readingLog.title'))).toBe(null)
    expect(screen.queryByText(t('dailyReportView.workLog.title'))).toBe(null)

    await user.click(getGoalTab(READING_GOAL_NAME))
    expect(screen.getByText(t('dailyReportView.readingLog.title'))).toBeTruthy()
    expect(screen.queryByText(t('dailyReportView.studyLog.title'))).toBe(null)
    expect(screen.queryByText(t('dailyReportView.workLog.title'))).toBe(null)

    await user.click(getGoalTab(WORK_GOAL_NAME))
    expect(screen.getByText(t('dailyReportView.workLog.title'))).toBeTruthy()
    expect(screen.queryByText(t('dailyReportView.readingLog.title'))).toBe(null)
  })

  it('keeps the comment section visible regardless of the selected tab', async () => {
    // コメントは日次記録単位（カテゴリを問わない）のためタブ切り替えの影響を受けない。
    const user = userEvent.setup()
    setupQueries([EXAM_GOAL, READING_GOAL, WORK_GOAL], buildFullRecord())
    renderPage()
    await waitForTitle()

    expect(screen.getByText(t('dailyReportView.comments.title'))).toBeTruthy()
    await user.click(getGoalTab(WORK_GOAL_NAME))
    expect(screen.getByText(t('dailyReportView.comments.title'))).toBeTruthy()
  })
})
