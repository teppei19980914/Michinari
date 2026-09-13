/** SC-06 日次報告（DailyReportPage）の振る舞いを固定する回帰テスト。
 *
 * このファイルは「画面の構造を変えても外から見た振る舞いが変わっていないこと」を守るための
 * 安全網である。純粋関数側（resolveDailyReportGuard等）のテストでは、フック順序・早期return
 * の位置・タブ切り替え時の下書き保持といった「コンポーネントの組み立て方に依存する仕様」を
 * 守れないため、描画テストとして置く。
 *
 * 特に次の4点は過去に実際の不具合が発生した箇所であり、必ず固定する。
 * - 確定はカテゴリごとに独立し、1カテゴリ確定しても他は入力・確定できる（仕様書1.1（改20））
 * - 着手中の全カテゴリが確定済みになったときだけダッシュボードへ遷移する（仕様変更2026-09-05）
 * - 全カテゴリ確定済み／入力可能期間外の日は閲覧画面へ自動転送する（仕様書7.2）
 * - 目標タブを切り替えても下書き入力は失われない（全目標分をローカル保持している）
 *
 * この画面自体はカバレッジの計測対象から外している（理由はvite.config.tsのcoverage.exclude
 * のコメントを参照）。本ファイルの目的は振る舞いの回帰検知であり、網羅率の担保は判定ロジック
 * を切り出した.ts側で行う。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  Link,
  Outlet,
  Route,
  RouterProvider,
  createMemoryRouter,
  createRoutesFromElements,
} from 'react-router-dom'
import { ROUTES, ROUTE_PATTERNS } from '../constants/routes'
import { ToastProvider } from '../components/Toast'
import { t } from '../locales/t'
import * as goalsApi from '../api/goals'
import * as recordsApi from '../api/records'
import * as resourcesApi from '../api/resources'
import type { BookRead, GoalRead, WorkAssignmentRead } from '../api/goals'
import type { DailyRecordRead, QuotaItemRead } from '../api/records'
import { DailyReportPage } from './DailyReportPage'

vi.mock('../api/goals')
vi.mock('../api/records')
vi.mock('../api/resources')

const LOGICAL_DATE = '2026-09-13'
/** 当日・前日のいずれでもない日（入力可能期間外。仕様書7.2）。 */
const OUT_OF_RANGE_DATE = '2026-09-10'

const EXAM_GOAL_NAME = 'exam-goal'
const READING_GOAL_NAME = 'reading-goal'
const WORK_GOAL_NAME = 'work-goal'

/** 遷移先の判別用マーカー。遷移先の画面そのものを描画するとその画面のデータ取得まで
 * 面倒を見ることになり、判定したい「どこへ遷移したか」が埋もれるため差し替える。 */
const VIEW_PAGE_MARKER = 'view-page'
const DASHBOARD_MARKER = 'dashboard-page'
/** 離脱警告（useBlocker）を発火させるためのアプリ内リンク。 */
const NAV_LINK_LABEL = 'nav-link'

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

const EXAM_GOAL = buildGoal(1, 'EXAM', EXAM_GOAL_NAME)
const READING_GOAL = buildGoal(2, 'READING', READING_GOAL_NAME)
const WORK_GOAL = buildGoal(3, 'WORK', WORK_GOAL_NAME)

const BOOK: BookRead = {
  id: 10,
  goal_id: READING_GOAL.id,
  title: 'book-title',
  author: null,
  total_pages: 200,
  start_date: LOGICAL_DATE,
  due_date: LOGICAL_DATE,
  remaining_days: 5,
  last_reading_date: null,
  current_streak: 0,
  current_page: null,
  progress_rate: null,
}

const WORK_ASSIGNMENT: WorkAssignmentRead = {
  id: 20,
  goal_id: WORK_GOAL.id,
  client_name: 'client-name',
  expected_content: '',
  start_date: LOGICAL_DATE,
  elapsed_days: 1,
  last_work_date: null,
  current_streak: 0,
  has_recent_monthly_report: false,
}

const QUOTA_ITEM: QuotaItemRead = {
  material_id: 30,
  material_name: 'material',
  unit_label: 'page',
  current_cycle: 1,
  planned_cycles: 3,
  daily_quota: 10,
  quality_metric_type: 'NONE',
  goal_id: EXAM_GOAL.id,
  goal_name: EXAM_GOAL_NAME,
  slot_defaults: [],
}

type ReportedStates = Partial<
  Pick<DailyRecordRead, 'exam_record_state' | 'reading_record_state' | 'work_record_state'>
>

function buildRecord(states: ReportedStates = {}): DailyRecordRead {
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
    ...states,
  }
}

type SetupOptions = {
  /** 着手中の目標。既定は3カテゴリすべて（＝目標タブが表示される構成）。 */
  goals?: GoalRead[]
  record?: DailyRecordRead
}

function setupQueries({ goals = [EXAM_GOAL, READING_GOAL, WORK_GOAL], record }: SetupOptions = {}) {
  const hasReading = goals.some((goal) => goal.category === 'READING')
  const hasWork = goals.some((goal) => goal.category === 'WORK')
  vi.mocked(goalsApi.listGoals).mockResolvedValue(goals)
  vi.mocked(goalsApi.listActiveReadingBooks).mockResolvedValue(
    hasReading ? [{ goal: READING_GOAL, book: BOOK }] : [],
  )
  vi.mocked(goalsApi.listActiveWorkAssignments).mockResolvedValue(
    hasWork ? [{ goal: WORK_GOAL, workAssignment: WORK_ASSIGNMENT }] : [],
  )
  vi.mocked(recordsApi.getRecord).mockResolvedValue(record ?? buildRecord())
  vi.mocked(recordsApi.getQuota).mockResolvedValue([QUOTA_ITEM])
  vi.mocked(recordsApi.getToday).mockResolvedValue({
    logical_date: LOGICAL_DATE,
    record_state: null,
  })
  vi.mocked(resourcesApi.listSlots).mockResolvedValue([])
}

/** 離脱警告（useBlocker）はdata routerでのみ動作するため、App.tsxと同じくcreateMemoryRouterで
 * 組み立てる（App.tsxのLayoutのコメント参照）。 */
function renderPage(targetDate: string = LOGICAL_DATE) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(
    createRoutesFromElements(
      <Route
        element={
          <>
            <Link to={ROUTES.dashboard}>{NAV_LINK_LABEL}</Link>
            <Outlet />
          </>
        }
      >
        <Route path={ROUTE_PATTERNS.dailyReport} element={<DailyReportPage />} />
        <Route path={ROUTE_PATTERNS.dailyReportView} element={<p>{VIEW_PAGE_MARKER}</p>} />
        <Route path={ROUTE_PATTERNS.dashboard} element={<p>{DASHBOARD_MARKER}</p>} />
      </Route>,
    ),
    { initialEntries: [ROUTES.dailyReport(targetDate)] },
  )
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  )
}

/** 目標タブ（GoalTabBar）はカテゴリ名と目標名を連結したラベルを持つ。 */
function getGoalTab(goalName: string) {
  return screen.getByRole('button', { name: new RegExp(goalName) })
}

async function waitForTitle() {
  await screen.findByText(t('dailyReport.title', { date: LOGICAL_DATE }))
}

beforeEach(() => {
  vi.clearAllMocks()
  setupQueries()
})

afterEach(() => {
  cleanup()
})

describe('DailyReportPage', () => {
  it('shows the loading label until every required query has settled', async () => {
    vi.mocked(recordsApi.getRecord).mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(await screen.findByText(t('common.loading'))).toBeTruthy()
  })

  it('shows an error message when a required query fails', async () => {
    vi.mocked(recordsApi.getRecord).mockRejectedValue(new Error('boom'))
    renderPage()
    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
  })

  it('redirects to the view screen when the target date is outside the input window', async () => {
    renderPage(OUT_OF_RANGE_DATE)
    expect(await screen.findByText(VIEW_PAGE_MARKER)).toBeTruthy()
  })

  it('redirects to the view screen when every started category is already reported', async () => {
    setupQueries({
      record: buildRecord({
        exam_record_state: 'REPORTED',
        reading_record_state: 'REPORTED',
        work_record_state: 'REPORTED',
      }),
    })
    renderPage()
    expect(await screen.findByText(VIEW_PAGE_MARKER)).toBeTruthy()
  })

  it('keeps the remaining categories reportable when only one category is finalized', async () => {
    const user = userEvent.setup()
    setupQueries({ record: buildRecord({ exam_record_state: 'REPORTED' }) })
    renderPage()
    await waitForTitle()

    // 確定済みの資格試験セクションは読み取り専用（確定ボタンなし）に切り替わる。
    expect(screen.getByText(t('dailyReport.confirmedBadge'))).toBeTruthy()
    expect(screen.queryByRole('button', { name: t('dailyReport.studyLog.finalizeButton') })).toBe(
      null,
    )

    // 未確定の読書・仕事は引き続き入力・確定できる（仕様書1.1（改20）の回帰）。
    await user.click(getGoalTab(READING_GOAL_NAME))
    expect(screen.getByLabelText(t('dailyReport.readingLog.recallLabel'))).toBeTruthy()
    expect(
      screen.getByRole('button', { name: t('dailyReport.readingLog.finalizeButton') }),
    ).toBeTruthy()

    await user.click(getGoalTab(WORK_GOAL_NAME))
    expect(screen.getByLabelText(t('dailyReport.workLog.bodyLabel'))).toBeTruthy()
    expect(
      screen.getByRole('button', { name: t('dailyReport.workLog.finalizeButton') }),
    ).toBeTruthy()
  })

  it('stays on the page when a finalize leaves another category unreported', async () => {
    const user = userEvent.setup()
    setupQueries({ record: buildRecord({ exam_record_state: 'REPORTED' }) })
    vi.mocked(recordsApi.finalizeReadingRecord).mockResolvedValue(
      buildRecord({ exam_record_state: 'REPORTED', reading_record_state: 'REPORTED' }),
    )
    renderPage()
    await waitForTitle()

    await user.click(getGoalTab(READING_GOAL_NAME))
    await user.click(
      screen.getByRole('button', { name: t('dailyReport.readingLog.finalizeButton') }),
    )

    await waitFor(() => expect(recordsApi.finalizeReadingRecord).toHaveBeenCalled())
    expect(screen.queryByText(DASHBOARD_MARKER)).toBe(null)
  })

  it('navigates to the dashboard when the last remaining category is finalized', async () => {
    const user = userEvent.setup()
    setupQueries({
      record: buildRecord({ exam_record_state: 'REPORTED', reading_record_state: 'REPORTED' }),
    })
    vi.mocked(recordsApi.finalizeWorkRecord).mockResolvedValue(
      buildRecord({
        exam_record_state: 'REPORTED',
        reading_record_state: 'REPORTED',
        work_record_state: 'REPORTED',
      }),
    )
    renderPage()
    await waitForTitle()

    await user.click(getGoalTab(WORK_GOAL_NAME))
    await user.click(screen.getByRole('button', { name: t('dailyReport.workLog.finalizeButton') }))

    expect(await screen.findByText(DASHBOARD_MARKER)).toBeTruthy()
  })

  /** カテゴリごとの「入力欄・送信先・積む下書き」の対応表。共通フック（useCategoryChat /
   * useCategoryFinalize）へ集約したため、ここが取り違うと3カテゴリ同時に壊れる。 */
  const CATEGORY_WIRING = [
    {
      name: 'exam',
      goalName: EXAM_GOAL_NAME,
      goalId: EXAM_GOAL.id,
      inputLabel: t('dailyReport.diary.bodyLabel'),
      chatStartLabel: t('dailyReport.chat.startButton'),
      finalizeLabel: t('dailyReport.studyLog.finalizeButton'),
      chatApi: recordsApi.sendChat,
      finalizeApi: recordsApi.finalizeRecord,
      purpose: 'DAILY_FEEDBACK',
      expectDraft: (draft: string) => ({
        diary_entries: [expect.objectContaining({ diary_body: draft })],
      }),
    },
    {
      name: 'reading',
      goalName: READING_GOAL_NAME,
      goalId: READING_GOAL.id,
      inputLabel: t('dailyReport.readingLog.recallLabel'),
      chatStartLabel: t('dailyReport.readingChat.startButton'),
      finalizeLabel: t('dailyReport.readingLog.finalizeButton'),
      chatApi: recordsApi.sendReadingChat,
      finalizeApi: recordsApi.finalizeReadingRecord,
      purpose: 'DAILY_FEEDBACK_READING',
      expectDraft: (draft: string) => ({
        reading_logs: [expect.objectContaining({ recall_body: draft })],
      }),
    },
    {
      name: 'work',
      goalName: WORK_GOAL_NAME,
      goalId: WORK_GOAL.id,
      inputLabel: t('dailyReport.workLog.bodyLabel'),
      chatStartLabel: t('dailyReport.workChat.startButton'),
      finalizeLabel: t('dailyReport.workLog.finalizeButton'),
      chatApi: recordsApi.sendWorkChat,
      finalizeApi: recordsApi.finalizeWorkRecord,
      purpose: 'DAILY_FEEDBACK_WORK',
      expectDraft: (draft: string) => ({
        work_logs: [expect.objectContaining({ body: draft })],
      }),
    },
  ] as const

  it.each(CATEGORY_WIRING)(
    'sends the $name draft to the $name chat endpoint with its own goal',
    async ({ goalName, goalId, chatStartLabel, chatApi, purpose }) => {
      const user = userEvent.setup()
      vi.mocked(chatApi).mockResolvedValue({
        record: buildRecord(),
        assistant_message: {
          id: 500,
          goal_id: goalId,
          purpose,
          role: 'ASSISTANT',
          content: `${purpose}-reply`,
          sequence: 0,
          created_at: '2026-09-13T00:00:00Z',
        },
        was_truncated: false,
      })
      renderPage()
      await waitForTitle()

      await user.click(getGoalTab(goalName))
      await user.click(screen.getByRole('button', { name: chatStartLabel }))

      expect(await screen.findByText(`${purpose}-reply`)).toBeTruthy()
      expect(chatApi).toHaveBeenCalledWith(
        LOGICAL_DATE,
        expect.objectContaining({ goal_id: goalId, message: null }),
      )
    },
  )

  it.each(CATEGORY_WIRING)(
    'finalizes $name with the draft typed into the $name section',
    async ({ goalName, inputLabel, finalizeLabel, finalizeApi, expectDraft }) => {
      const user = userEvent.setup()
      vi.mocked(finalizeApi).mockResolvedValue(buildRecord())
      renderPage()
      await waitForTitle()

      await user.click(getGoalTab(goalName))
      await user.type(screen.getByLabelText(inputLabel), 'draft-value')
      await user.click(screen.getByRole('button', { name: finalizeLabel }))

      await waitFor(() =>
        expect(finalizeApi).toHaveBeenCalledWith(
          LOGICAL_DATE,
          expect.objectContaining(expectDraft('draft-value')),
        ),
      )
    },
  )

  it('shows the truncation notice only in the category whose reply was truncated', async () => {
    const user = userEvent.setup()
    vi.mocked(recordsApi.sendReadingChat).mockResolvedValue({
      record: buildRecord(),
      assistant_message: {
        id: 501,
        goal_id: READING_GOAL.id,
        purpose: 'DAILY_FEEDBACK_READING',
        role: 'ASSISTANT',
        content: 'reading-reply',
        sequence: 0,
        created_at: '2026-09-13T00:00:00Z',
      },
      was_truncated: true,
    })
    renderPage()
    await waitForTitle()

    await user.click(getGoalTab(READING_GOAL_NAME))
    await user.click(screen.getByRole('button', { name: t('dailyReport.readingChat.startButton') }))
    expect(await screen.findByText(t('dailyReport.chat.truncatedNotice'))).toBeTruthy()

    // 省略通知はカテゴリごとに独立して保持する。
    await user.click(getGoalTab(WORK_GOAL_NAME))
    expect(screen.queryByText(t('dailyReport.chat.truncatedNotice'))).toBe(null)
  })

  it('keeps the draft when the AI call fails', async () => {
    // 仕様書16.7「AI呼び出しが失敗しても実績入力が失われない」。
    const user = userEvent.setup()
    vi.mocked(recordsApi.sendChat).mockRejectedValue(new Error('boom'))
    renderPage()
    await waitForTitle()

    await user.type(screen.getByLabelText(t('dailyReport.diary.bodyLabel')), 'draft-exam')
    await user.click(screen.getByRole('button', { name: t('dailyReport.chat.startButton') }))

    await waitFor(() => expect(recordsApi.sendChat).toHaveBeenCalled())
    expect(
      (screen.getByLabelText(t('dailyReport.diary.bodyLabel')) as HTMLTextAreaElement).value,
    ).toBe('draft-exam')
  })

  it('keeps drafts of goals that are not currently selected', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForTitle()

    await user.type(screen.getByLabelText(t('dailyReport.diary.bodyLabel')), 'draft-exam')

    await user.click(getGoalTab(READING_GOAL_NAME))
    await user.type(screen.getByLabelText(t('dailyReport.readingLog.recallLabel')), 'draft-reading')

    // 資格試験タブへ戻しても入力は保持されている（全目標分をローカル保持しているため）。
    await user.click(getGoalTab(EXAM_GOAL_NAME))
    expect(
      (screen.getByLabelText(t('dailyReport.diary.bodyLabel')) as HTMLTextAreaElement).value,
    ).toBe('draft-exam')

    await user.click(getGoalTab(READING_GOAL_NAME))
    expect(
      (screen.getByLabelText(t('dailyReport.readingLog.recallLabel')) as HTMLTextAreaElement).value,
    ).toBe('draft-reading')
  })

  it('warns before leaving the page while an unsaved draft exists', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForTitle()

    await user.type(screen.getByLabelText(t('dailyReport.diary.bodyLabel')), 'draft-exam')
    await user.click(screen.getByRole('link', { name: NAV_LINK_LABEL }))

    expect(await screen.findByText(t('dailyReport.leaveConfirm.title'))).toBeTruthy()
    expect(screen.queryByText(DASHBOARD_MARKER)).toBe(null)
  })

  it('does not warn when there is no unsaved draft', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForTitle()

    await user.click(screen.getByRole('link', { name: NAV_LINK_LABEL }))

    expect(await screen.findByText(DASHBOARD_MARKER)).toBeTruthy()
  })

  it('stays on the page when the leave warning is dismissed', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForTitle()

    await user.type(screen.getByLabelText(t('dailyReport.diary.bodyLabel')), 'draft-exam')
    await user.click(screen.getByRole('link', { name: NAV_LINK_LABEL }))
    await screen.findByText(t('dailyReport.leaveConfirm.title'))

    await user.click(screen.getByRole('button', { name: t('dailyReport.leaveConfirm.stay') }))

    expect(screen.queryByText(t('dailyReport.leaveConfirm.title'))).toBe(null)
    expect(screen.queryByText(DASHBOARD_MARKER)).toBe(null)
    expect(
      (screen.getByLabelText(t('dailyReport.diary.bodyLabel')) as HTMLTextAreaElement).value,
    ).toBe('draft-exam')
  })

  it('leaves the page when the leave warning is confirmed', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForTitle()

    await user.type(screen.getByLabelText(t('dailyReport.diary.bodyLabel')), 'draft-exam')
    await user.click(screen.getByRole('link', { name: NAV_LINK_LABEL }))
    await screen.findByText(t('dailyReport.leaveConfirm.title'))

    await user.click(screen.getByRole('button', { name: t('dailyReport.leaveConfirm.leave') }))

    expect(await screen.findByText(DASHBOARD_MARKER)).toBeTruthy()
  })

  it('does not warn on the navigation caused by finalizing the last category', async () => {
    // 確定成功による遷移まで離脱警告でブロックすると、確定したのに画面から出られなくなる
    // （finalizedRefの役割）。下書きを残したまま確定させて、警告が出ないことを固定する。
    const user = userEvent.setup()
    setupQueries({
      record: buildRecord({ exam_record_state: 'REPORTED', reading_record_state: 'REPORTED' }),
    })
    vi.mocked(recordsApi.finalizeWorkRecord).mockResolvedValue(
      buildRecord({
        exam_record_state: 'REPORTED',
        reading_record_state: 'REPORTED',
        work_record_state: 'REPORTED',
      }),
    )
    renderPage()
    await waitForTitle()

    await user.click(getGoalTab(WORK_GOAL_NAME))
    await user.type(screen.getByLabelText(t('dailyReport.workLog.bodyLabel')), 'draft-work')
    await user.click(screen.getByRole('button', { name: t('dailyReport.workLog.finalizeButton') }))

    expect(await screen.findByText(DASHBOARD_MARKER)).toBeTruthy()
    expect(screen.queryByText(t('dailyReport.leaveConfirm.title'))).toBe(null)
  })

  it('does not warn about drafts of categories that are already finalized', async () => {
    // 確定済みカテゴリの下書きが残っていても、既にサーバへ反映済みのため警告対象にしない。
    const user = userEvent.setup()
    setupQueries({
      record: buildRecord({
        exam_record_state: 'REPORTED',
        diary_entries: [
          {
            goal_id: EXAM_GOAL.id,
            goal_name: EXAM_GOAL_NAME,
            diary_body: 'already-reported',
            diary_learned: null,
          },
        ],
      }),
    })
    renderPage()
    await waitForTitle()

    await user.click(screen.getByRole('link', { name: NAV_LINK_LABEL }))

    expect(await screen.findByText(DASHBOARD_MARKER)).toBeTruthy()
  })

  it('keeps the study log draft of a goal that is not currently selected', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForTitle()

    const amountInput = screen.getByLabelText(
      t('dailyReport.studyLog.amountLabel', { unit: QUOTA_ITEM.unit_label }),
    )
    await user.clear(amountInput)
    await user.type(amountInput, '12')

    await user.click(getGoalTab(READING_GOAL_NAME))
    await user.click(getGoalTab(EXAM_GOAL_NAME))

    expect(
      (
        screen.getByLabelText(
          t('dailyReport.studyLog.amountLabel', { unit: QUOTA_ITEM.unit_label }),
        ) as HTMLInputElement
      ).value,
    ).toBe('12')
  })

  it('requests the record of the date in the url', async () => {
    renderPage()
    await waitForTitle()

    expect(recordsApi.getRecord).toHaveBeenCalledWith(LOGICAL_DATE)
    expect(recordsApi.getQuota).toHaveBeenCalledWith(LOGICAL_DATE)
  })
})
