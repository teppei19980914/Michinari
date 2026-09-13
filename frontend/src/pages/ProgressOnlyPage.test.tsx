/** SC-07 進捗のみ登録（ProgressOnlyPage）の振る舞いを固定する回帰テスト。
 *
 * この画面は今回のリファクタで、重複していた時間枠名の取得（useSlotNames）と確定後の
 * キャッシュ無効化（invalidateDailyRecordCaches）を共通化した。転送ガードと登録の経路を
 * 固定して、共通化による退行を検知できるようにする。
 *
 * カバレッジの扱いは DailyReportPage.test.tsx と同じ（vite.config.ts の coverage.exclude）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { ROUTES, ROUTE_PATTERNS } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { t } from '../locales/t'
import * as recordsApi from '../api/records'
import * as resourcesApi from '../api/resources'
import type { DailyRecordRead, QuotaItemRead } from '../api/records'
import { ProgressOnlyPage } from './ProgressOnlyPage'

vi.mock('../api/records')
vi.mock('../api/resources')

const LOGICAL_DATE = '2026-09-13'
/** 未来日は進捗のみ登録もできない（仕様書7.2）。 */
const FUTURE_DATE = '2026-09-14'
const VIEW_PAGE_MARKER = 'view-page'
const DASHBOARD_MARKER = 'dashboard-page'

const QUOTA_ITEM = {
  material_id: 30,
  material_name: 'material',
  unit_label: 'page',
  current_cycle: 1,
  planned_cycles: 3,
  daily_quota: 10,
  quality_metric_type: 'NONE',
  goal_id: 1,
  goal_name: 'exam-goal',
  slot_defaults: [],
} as unknown as QuotaItemRead

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

function setupQueries(record: DailyRecordRead = buildRecord()) {
  vi.mocked(recordsApi.getRecord).mockResolvedValue(record)
  vi.mocked(recordsApi.getQuota).mockResolvedValue([QUOTA_ITEM])
  vi.mocked(recordsApi.getToday).mockResolvedValue({
    logical_date: LOGICAL_DATE,
    record_state: null,
  })
  vi.mocked(resourcesApi.listSlots).mockResolvedValue([])
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

    expect(await screen.findByText(t('progressOnly.title', { date: LOGICAL_DATE }))).toBeTruthy()
    expect(screen.getByRole('button', { name: t('progressOnly.registerButton') })).toBeTruthy()
  })

  it('redirects to the view screen for a future date', async () => {
    renderPage(FUTURE_DATE)

    expect(await screen.findByText(VIEW_PAGE_MARKER)).toBeTruthy()
  })

  it('redirects to the view screen when the exam category is already finalized', async () => {
    setupQueries(buildRecord({ exam_record_state: 'REPORTED' }))
    renderPage()

    expect(await screen.findByText(VIEW_PAGE_MARKER)).toBeTruthy()
  })

  it('keeps the register button disabled until something is entered', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(t('progressOnly.title', { date: LOGICAL_DATE }))

    const registerButton = screen.getByRole('button', {
      name: t('progressOnly.registerButton'),
    }) as HTMLButtonElement
    expect(registerButton.disabled).toBe(true)

    await user.type(
      screen.getByLabelText(t('dailyReport.studyLog.amountLabel', { unit: QUOTA_ITEM.unit_label })),
      '5',
    )
    expect(registerButton.disabled).toBe(false)
  })

  it('registers the entered progress and returns to the dashboard', async () => {
    const user = userEvent.setup()
    vi.mocked(recordsApi.registerProgress).mockResolvedValue(buildRecord())
    renderPage()
    await screen.findByText(t('progressOnly.title', { date: LOGICAL_DATE }))

    await user.type(
      screen.getByLabelText(t('dailyReport.studyLog.amountLabel', { unit: QUOTA_ITEM.unit_label })),
      '5',
    )
    await user.click(screen.getByRole('button', { name: t('progressOnly.registerButton') }))

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
