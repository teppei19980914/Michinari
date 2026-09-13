/** SC-07 進捗のみ登録（ProgressOnlyPage）の振る舞いを固定する回帰テスト。
 *
 * この画面は資格試験（study_logs）しか送らない実装だったため、読書・仕事の目標しか持たない
 * 利用者には入力欄の無い画面が表示されていた。3カテゴリ対応（仕様書1.1（改21））にあたり、
 * 次の点を固定する。
 * - 着手中のカテゴリの入力欄をすべて表示し、1回の登録でまとめて送る
 * - 確定済みカテゴリは入力欄を出さず実績も送らない（送るとIMMUTABLE_RECORDで全体が失敗する）
 * - 未来日／登録できるカテゴリが残っていない日は閲覧画面へ転送する
 *
 * カバレッジの扱いは DailyReportPage.test.tsx と同じ（vite.config.ts の coverage.exclude）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { ROUTES, ROUTE_PATTERNS } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { t } from '../locales/t'
import * as goalsApi from '../api/goals'
import * as recordsApi from '../api/records'
import * as resourcesApi from '../api/resources'
import type { BookRead, GoalRead, WorkAssignmentRead } from '../api/goals'
import type { DailyRecordRead, QuotaItemRead } from '../api/records'
import type { ResourceSlotRead } from '../api/resources'
import { ProgressOnlyPage } from './ProgressOnlyPage'

vi.mock('../api/goals')
vi.mock('../api/records')
vi.mock('../api/resources')

const LOGICAL_DATE = '2026-09-13'
/** 未来日は進捗のみ登録もできない（仕様書7.2）。 */
const FUTURE_DATE = '2026-09-14'
const VIEW_PAGE_MARKER = 'view-page'
const DASHBOARD_MARKER = 'dashboard-page'

function buildGoal(id: number, category: GoalRead['category'], name: string): GoalRead {
  return {
    id,
    category,
    name,
    start_date: LOGICAL_DATE,
    status: 'ACTIVE',
    memo: null,
    activated_at: null,
    closed_at: null,
    archived_at: null,
  }
}

const EXAM_GOAL = buildGoal(1, 'EXAM', 'exam-goal')
const READING_GOAL = buildGoal(2, 'READING', 'reading-goal')
const WORK_GOAL = buildGoal(3, 'WORK', 'work-goal')

const BOOK = {
  id: 10,
  goal_id: READING_GOAL.id,
  title: 'book-title',
  total_pages: 200,
} as unknown as BookRead

const WORK_ASSIGNMENT = {
  id: 20,
  goal_id: WORK_GOAL.id,
  client_name: 'client-name',
} as unknown as WorkAssignmentRead

const SLOT_NAME = 'morning-slot'
const SLOT = { id: 40, name: SLOT_NAME } as ResourceSlotRead

const QUOTA_ITEM = {
  material_id: 30,
  material_name: 'material',
  unit_label: 'page',
  current_cycle: 1,
  planned_cycles: 3,
  daily_quota: 10,
  quality_metric_type: 'NONE',
  goal_id: EXAM_GOAL.id,
  goal_name: 'exam-goal',
  slot_defaults: [{ slot_id: SLOT.id, slot_name: SLOT_NAME, minutes: 0 }],
} as unknown as QuotaItemRead

/** 確定済みの資格勉強が持つ保存済み実績。下書きはこの値で初期化される
 * （initStudyLogFormValues）ため、送信対象から外さないと確定済みカテゴリへ再送してしまう。 */
const REPORTED_STUDY_LOG = {
  id: 1,
  material_id: QUOTA_ITEM.material_id,
  amount_completed: 7,
  cycle_number: 1,
  quality_value: null,
  minutes_spent: null,
  slot_minutes: [],
} as unknown as DailyRecordRead['study_logs'][number]

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

/** 着手中の目標の組み合わせを指定して取得をモックする。既定は資格試験のみ（従来の前提）。 */
function setupQueries(options: { record?: DailyRecordRead; goals?: GoalRead[] } = {}) {
  const goals = options.goals ?? [EXAM_GOAL]
  const hasCategory = (category: GoalRead['category']) =>
    goals.some((goal) => goal.category === category)

  vi.mocked(recordsApi.getRecord).mockResolvedValue(options.record ?? buildRecord())
  vi.mocked(recordsApi.getQuota).mockResolvedValue(hasCategory('EXAM') ? [QUOTA_ITEM] : [])
  vi.mocked(recordsApi.getToday).mockResolvedValue({
    logical_date: LOGICAL_DATE,
    record_state: null,
  })
  vi.mocked(resourcesApi.listSlots).mockResolvedValue([SLOT])
  vi.mocked(goalsApi.listGoals).mockResolvedValue(goals)
  vi.mocked(goalsApi.listActiveReadingBooks).mockResolvedValue(
    hasCategory('READING') ? [{ goal: READING_GOAL, book: BOOK }] : [],
  )
  vi.mocked(goalsApi.listActiveWorkAssignments).mockResolvedValue(
    hasCategory('WORK') ? [{ goal: WORK_GOAL, workAssignment: WORK_ASSIGNMENT }] : [],
  )
}

function renderPage(targetDate: string = LOGICAL_DATE) {
  renderWithProviders(
    <Routes>
      <Route path={ROUTE_PATTERNS.dailyReportProgress} element={<ProgressOnlyPage />} />
      <Route path={ROUTE_PATTERNS.dailyReportView} element={<p>{VIEW_PAGE_MARKER}</p>} />
      <Route path={ROUTE_PATTERNS.dashboard} element={<p>{DASHBOARD_MARKER}</p>} />
    </Routes>,
    { initialEntries: [ROUTES.dailyReportProgress(targetDate)] },
  )
}

function registerButton(): HTMLButtonElement {
  return screen.getByRole('button', { name: t('progressOnly.registerButton') }) as HTMLButtonElement
}

function waitForPage() {
  return screen.findByText(t('progressOnly.title', { date: LOGICAL_DATE }))
}

beforeEach(() => {
  vi.clearAllMocks()
  setupQueries()
})

afterEach(() => {
  cleanup()
})

describe('ProgressOnlyPage', () => {
  it('shows the input form for a date that can still be registered', async () => {
    renderPage()

    expect(await waitForPage()).toBeTruthy()
    expect(registerButton()).toBeTruthy()
  })

  it('redirects to the view screen for a future date', async () => {
    renderPage(FUTURE_DATE)

    expect(await screen.findByText(VIEW_PAGE_MARKER)).toBeTruthy()
  })

  it('redirects to the view screen when the only category in progress is finalized', async () => {
    setupQueries({ record: buildRecord({ exam_record_state: 'REPORTED' }) })
    renderPage()

    expect(await screen.findByText(VIEW_PAGE_MARKER)).toBeTruthy()
  })

  it('keeps the register button disabled until something is entered', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPage()

    expect(registerButton().disabled).toBe(true)

    await user.type(
      screen.getByLabelText(t('dailyReport.studyLog.amountLabel', { unit: QUOTA_ITEM.unit_label })),
      '5',
    )
    expect(registerButton().disabled).toBe(false)
  })

  it('registers the entered progress and returns to the dashboard', async () => {
    const user = userEvent.setup()
    vi.mocked(recordsApi.registerProgress).mockResolvedValue(buildRecord())
    renderPage()
    await waitForPage()

    await user.type(
      screen.getByLabelText(t('dailyReport.studyLog.amountLabel', { unit: QUOTA_ITEM.unit_label })),
      '5',
    )
    await user.click(registerButton())

    await waitFor(() =>
      expect(recordsApi.registerProgress).toHaveBeenCalledWith(
        LOGICAL_DATE,
        expect.objectContaining({
          study_logs: [expect.objectContaining({ amount_completed: 5 })],
        }),
      ),
    )
    expect(await screen.findByText(DASHBOARD_MARKER)).toBeTruthy()
  })
})

/** 3カテゴリ対応（仕様書1.1（改21））で追加した振る舞い。 */
describe('ProgressOnlyPage（読書・仕事の目標）', () => {
  it('registers reading progress for a user who has no exam goal', async () => {
    const user = userEvent.setup()
    setupQueries({ goals: [READING_GOAL] })
    vi.mocked(recordsApi.registerProgress).mockResolvedValue(buildRecord())
    renderPage()
    await waitForPage()

    expect(screen.queryByText(t('progressOnly.studyLog.title'))).toBe(null)
    await user.type(screen.getByLabelText(t('dailyReport.readingLog.recallLabel')), 'today I read')
    await user.click(registerButton())

    await waitFor(() =>
      expect(recordsApi.registerProgress).toHaveBeenCalledWith(
        LOGICAL_DATE,
        expect.objectContaining({
          reading_logs: [expect.objectContaining({ book_id: BOOK.id })],
          study_logs: [],
        }),
      ),
    )
  })

  it('registers work progress for a user who has no exam goal', async () => {
    const user = userEvent.setup()
    setupQueries({ goals: [WORK_GOAL] })
    vi.mocked(recordsApi.registerProgress).mockResolvedValue(buildRecord())
    renderPage()
    await waitForPage()

    await user.type(screen.getByLabelText(t('dailyReport.workLog.bodyLabel')), 'today I worked')
    await user.click(registerButton())

    await waitFor(() =>
      expect(recordsApi.registerProgress).toHaveBeenCalledWith(
        LOGICAL_DATE,
        expect.objectContaining({
          work_logs: [expect.objectContaining({ work_assignment_id: WORK_ASSIGNMENT.id })],
        }),
      ),
    )
  })

  it('shows every category in progress at once', async () => {
    setupQueries({ goals: [EXAM_GOAL, READING_GOAL, WORK_GOAL] })
    renderPage()
    await waitForPage()

    expect(screen.getByText(t('progressOnly.studyLog.title'))).toBeTruthy()
    expect(screen.getByText(t('progressOnly.readingLog.title'))).toBeTruthy()
    expect(screen.getByText(t('progressOnly.workLog.title'))).toBeTruthy()
  })

  // 資格勉強を確定した日でも、読書が未確定なら進捗を登録できなければならない
  // （2026-09-12に日次報告で是正した不具合と同型）。
  it('keeps registering possible for the categories that are not finalized yet', async () => {
    const user = userEvent.setup()
    setupQueries({
      goals: [EXAM_GOAL, READING_GOAL],
      record: buildRecord({
        exam_record_state: 'REPORTED',
        study_logs: [REPORTED_STUDY_LOG],
      }),
    })
    vi.mocked(recordsApi.registerProgress).mockResolvedValue(buildRecord())
    renderPage()
    await waitForPage()

    expect(screen.queryByText(t('progressOnly.studyLog.title'))).toBe(null)
    await user.type(screen.getByLabelText(t('dailyReport.readingLog.recallLabel')), 'recall')
    await user.click(registerButton())

    // 確定済みの資格勉強の実績を積むとサーバに拒否され、読書の登録まで失敗する。
    await waitFor(() =>
      expect(recordsApi.registerProgress).toHaveBeenCalledWith(LOGICAL_DATE, {
        study_logs: [],
        reading_logs: [expect.objectContaining({ recall_body: 'recall' })],
        work_logs: [],
      }),
    )
  })
})

/** 時間枠ごとの時間入力（仕様書6.6「実績入力の構成は6.5と共通」）。 */
describe('ProgressOnlyPage（時間枠ごとの時間）', () => {
  it('sends the minutes entered per time slot for a material', async () => {
    const user = userEvent.setup()
    vi.mocked(recordsApi.registerProgress).mockResolvedValue(buildRecord())
    renderPage()
    await waitForPage()

    await user.type(
      screen.getByLabelText(t('dailyReport.studyLog.amountLabel', { unit: QUOTA_ITEM.unit_label })),
      '5',
    )
    await user.type(screen.getByLabelText(new RegExp(SLOT_NAME)), '30')
    await user.click(registerButton())

    await waitFor(() =>
      expect(recordsApi.registerProgress).toHaveBeenCalledWith(
        LOGICAL_DATE,
        expect.objectContaining({
          study_logs: [
            expect.objectContaining({ slot_minutes: [{ slot_id: SLOT.id, minutes: 30 }] }),
          ],
        }),
      ),
    )
  })

  // 読書は配分済みの枠を持たないため、「他の時間枠を追加」で枠を足してから入力する
  // （仕様書6.5「未配分スロットの追加」）。
  it('sends the reading minutes entered after adding a time slot', async () => {
    const user = userEvent.setup()
    setupQueries({ goals: [READING_GOAL] })
    vi.mocked(recordsApi.registerProgress).mockResolvedValue(buildRecord())
    renderPage()
    await waitForPage()

    await user.type(screen.getByLabelText(t('dailyReport.readingLog.recallLabel')), 'recall')
    await user.selectOptions(
      screen.getByLabelText(t('dailyReport.studyLog.addSlotLabel')),
      String(SLOT.id),
    )
    await user.type(screen.getByLabelText(new RegExp(SLOT_NAME)), '20')
    await user.click(registerButton())

    await waitFor(() =>
      expect(recordsApi.registerProgress).toHaveBeenCalledWith(
        LOGICAL_DATE,
        expect.objectContaining({
          reading_logs: [
            expect.objectContaining({ slot_minutes: [{ slot_id: SLOT.id, minutes: 20 }] }),
          ],
        }),
      ),
    )
  })
})
