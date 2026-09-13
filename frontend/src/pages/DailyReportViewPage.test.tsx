/** SC-08 日次報告閲覧（DailyReportViewPage）のセクション表示規則を固定する回帰テスト。
 *
 * 入力画面（SC-06）と閲覧画面（SC-08）で表示条件がずれると、同じ日の記録が画面によって
 * 違って見える。共通の判定（features/record/sectionVisibility.ts）へ寄せるにあたり、
 * この画面の従来の見え方を先に固定しておく。
 *
 * カバレッジの扱いは DailyReportPage.test.tsx と同じ（vite.config.ts の coverage.exclude）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { ROUTES, ROUTE_PATTERNS } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { t } from '../locales/t'
import * as goalsApi from '../api/goals'
import * as recordsApi from '../api/records'
import type { BookRead, GoalRead, WorkAssignmentRead } from '../api/goals'
import type { ChatMessageRead, DailyRecordRead, QuotaItemRead } from '../api/records'
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
const CLIENT_NAME = 'client-name'
const WORK_ASSIGNMENT = {
  id: 20,
  goal_id: WORK_GOAL.id,
  client_name: CLIENT_NAME,
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

/** AI対話履歴。用途（purpose）とgoal_idの組み合わせで表示先が決まるため、
 * 本文にどのメッセージかが分かる文字列を入れて取り違えを検出できるようにする。 */
function buildChatMessage(
  id: number,
  purpose: ChatMessageRead['purpose'],
  goalId: number | null,
  content: string,
): ChatMessageRead {
  return {
    id,
    sequence: id,
    role: 'ASSISTANT',
    purpose,
    goal_id: goalId,
    content,
    created_at: '2026-09-13T12:00:00',
  }
}

const EXAM_MESSAGE = buildChatMessage(60, 'DAILY_FEEDBACK', EXAM_GOAL.id, 'exam-feedback')
const READING_MESSAGE = buildChatMessage(
  61,
  'DAILY_FEEDBACK_READING',
  READING_GOAL.id,
  'reading-feedback',
)
const WORK_MESSAGE = buildChatMessage(62, 'DAILY_FEEDBACK_WORK', WORK_GOAL.id, 'work-feedback')
/** 目標単位の会話へ分離する前（Phase26以前）に記録された、goal_idを持たないメッセージ。 */
const LEGACY_EXAM_MESSAGE = buildChatMessage(63, 'DAILY_FEEDBACK', null, 'legacy-exam-feedback')
/** 別の資格試験目標宛てのメッセージ。タブで選択していない間は出してはいけない。 */
const OTHER_GOAL_EXAM_MESSAGE = buildChatMessage(
  64,
  'DAILY_FEEDBACK',
  EXAM_GOAL.id + 100,
  'other-goal-feedback',
)

/** 3カテゴリすべてに記録がある日。着手中の目標も3件のため目標タブが表示される。 */
function buildFullRecord(): DailyRecordRead {
  return buildRecord({
    reading_logs: [READING_LOG],
    work_logs: [WORK_LOG],
    diary_entries: [
      { goal_id: EXAM_GOAL.id, goal_name: EXAM_GOAL_NAME, diary_body: 'diary-body', diary_learned: null },
    ],
    chat_messages: [
      EXAM_MESSAGE,
      READING_MESSAGE,
      WORK_MESSAGE,
      LEGACY_EXAM_MESSAGE,
      OTHER_GOAL_EXAM_MESSAGE,
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

  it('shows the diary only while the exam tab is selected', async () => {
    // 日記は資格試験の入力欄にしかないため、タブがある間は資格試験のタブでのみ出す。
    const user = userEvent.setup()
    setupQueries([EXAM_GOAL, READING_GOAL, WORK_GOAL], buildFullRecord())
    renderPage()
    await waitForTitle()

    expect(screen.getByText(t('dailyReportView.diary.title'))).toBeTruthy()
    await user.click(getGoalTab(READING_GOAL_NAME))
    expect(screen.queryByText(t('dailyReportView.diary.title'))).toBe(null)
  })

  it('hides the diary section when every entry is blank', async () => {
    // 本文も学んだことも空のエントリは「書かれていない」扱いにする。
    setupQueries(
      [EXAM_GOAL],
      buildRecord({
        diary_entries: [
          { goal_id: EXAM_GOAL.id, goal_name: EXAM_GOAL_NAME, diary_body: null, diary_learned: null },
        ],
      }),
    )
    renderPage()
    await waitForTitle()

    expect(screen.queryByText(t('dailyReportView.diary.title'))).toBe(null)
  })

  it('files each feedback message under the chat history of its own category', async () => {
    const user = userEvent.setup()
    setupQueries([EXAM_GOAL, READING_GOAL, WORK_GOAL], buildFullRecord())
    renderPage()
    await waitForTitle()

    // 資格試験タブ: 資格試験宛てのみ。読書・仕事宛てが混ざってはいけない。
    expect(screen.getByText(t('dailyReportView.chatHistory.title'))).toBeTruthy()
    expect(screen.getByText(EXAM_MESSAGE.content)).toBeTruthy()
    expect(screen.queryByText(READING_MESSAGE.content)).toBe(null)
    expect(screen.queryByText(WORK_MESSAGE.content)).toBe(null)

    await user.click(getGoalTab(READING_GOAL_NAME))
    expect(screen.getByText(t('dailyReportView.readingChatHistory.title'))).toBeTruthy()
    expect(screen.getByText(READING_MESSAGE.content)).toBeTruthy()
    expect(screen.queryByText(t('dailyReportView.chatHistory.title'))).toBe(null)

    await user.click(getGoalTab(WORK_GOAL_NAME))
    expect(screen.getByText(t('dailyReportView.workChatHistory.title'))).toBeTruthy()
    expect(screen.getByText(WORK_MESSAGE.content)).toBeTruthy()
    expect(screen.queryByText(t('dailyReportView.readingChatHistory.title'))).toBe(null)
  })

  it('narrows the chat history to the selected goal but keeps the messages with no goal', async () => {
    // goal_idを持たないメッセージは移行前のレガシーのため、どの目標を選んでいても表示する。
    // 別目標宛てのメッセージは選択中でない限り出さない（Phase26の絞り込み）。
    setupQueries([EXAM_GOAL, READING_GOAL, WORK_GOAL], buildFullRecord())
    renderPage()
    await waitForTitle()

    expect(screen.getByText(LEGACY_EXAM_MESSAGE.content)).toBeTruthy()
    expect(screen.queryByText(OTHER_GOAL_EXAM_MESSAGE.content)).toBe(null)
  })

  it('shows every goal’s feedback when there is no goal tab bar', async () => {
    // タブが無い間はカテゴリのみで絞り込む（1目標のみ、または全目標クローズ済みの日でも
    // その日の記録を漏れなく表示するため）。
    setupQueries([EXAM_GOAL], buildFullRecord())
    renderPage()
    await waitForTitle()

    expect(screen.getByText(EXAM_MESSAGE.content)).toBeTruthy()
    expect(screen.getByText(LEGACY_EXAM_MESSAGE.content)).toBeTruthy()
    expect(screen.getByText(OTHER_GOAL_EXAM_MESSAGE.content)).toBeTruthy()
    expect(screen.getByText(READING_MESSAGE.content)).toBeTruthy()
    expect(screen.getByText(WORK_MESSAGE.content)).toBeTruthy()
  })

  it('hides a chat history that has no message', async () => {
    setupQueries([EXAM_GOAL], buildRecord())
    renderPage()
    await waitForTitle()

    expect(screen.queryByText(t('dailyReportView.chatHistory.title'))).toBe(null)
    expect(screen.queryByText(t('dailyReportView.readingChatHistory.title'))).toBe(null)
    expect(screen.queryByText(t('dailyReportView.workChatHistory.title'))).toBe(null)
  })

  it('labels the logged material, book and work assignment', async () => {
    // 実績はIDで記録されており、名称は別のクエリから引く。取り違えると誰の記録か分からなくなる。
    setupQueries(
      [EXAM_GOAL],
      buildRecord({
        study_logs: [
          {
            id: 70,
            material_id: QUOTA_ITEM.material_id,
            amount_completed: 5,
            cycle_number: 1,
            minutes_spent: null,
            slot_minutes: [],
            quality_value: null,
          },
        ],
        reading_logs: [READING_LOG],
        work_logs: [WORK_LOG],
      }),
    )
    // 名称の引き当て元（書籍・案件の一覧）は目標の種別とは別に取得されるため、
    // 着手中の目標が資格試験だけでも引き当てられる状態を作る。
    vi.mocked(goalsApi.listActiveReadingBooks).mockResolvedValue([
      { goal: READING_GOAL, book: BOOK },
    ])
    vi.mocked(goalsApi.listActiveWorkAssignments).mockResolvedValue([
      { goal: WORK_GOAL, workAssignment: WORK_ASSIGNMENT },
    ])
    renderPage()
    await waitForTitle()

    expect(screen.getByText(new RegExp(QUOTA_ITEM.material_name))).toBeTruthy()
    expect(screen.getByText(new RegExp(BOOK.title))).toBeTruthy()
    expect(screen.getByText(new RegExp(CLIENT_NAME))).toBeTruthy()
  })

  it('keeps waiting while only the goal list is still loading', async () => {
    // 目標の一覧が届く前に本文を描画すると、タブの有無が決まらないまま全カテゴリを
    // 出してしまい、直後に選択中のタブの分だけへ切り替わる。他のクエリが揃っても
    // 目標の一覧が揃うまでは待つ。
    setupQueries([EXAM_GOAL, READING_GOAL, WORK_GOAL], buildFullRecord())
    vi.mocked(goalsApi.listGoals).mockReturnValue(new Promise(() => {}))
    renderPage()

    // 目標の一覧以外が解決し、その結果が反映されるまで待つ。
    await waitFor(() => expect(recordsApi.getRecord).toHaveBeenCalled())
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    expect(screen.getByText(t('common.loading'))).toBeTruthy()
    expect(screen.queryByText(t('dailyReportView.title', { date: TARGET_DATE }))).toBe(null)
  })

  it('shows the error message when the record cannot be read', async () => {
    setupQueries([EXAM_GOAL], buildRecord())
    vi.mocked(recordsApi.getRecord).mockRejectedValue(new Error('boom'))
    renderPage()

    await screen.findByText(t('errors.default'))
    expect(screen.queryByText(t('dailyReportView.title', { date: TARGET_DATE }))).toBe(null)
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
