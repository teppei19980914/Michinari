/** ダッシュボードの読み込み・エラー表示と、選択中の目標での絞り込みを固定する（Phase 35）。
 *
 * 絞り込みが壊れると、複数目標が同時進行しているときに他の目標の進捗・ノルマが混ざって
 * 表示される。Phase25・26 で実際に起きた「別目標の情報が混在する」不具合と同じ経路であり、
 * 数字が出ている以上は画面を見ても気づきにくいため、テストで固定する。
 *
 * 目標非依存の本日の状態（`record_state`）は目標を切り替えても変わらないことも併せて確かめる。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, type InitialEntry } from 'react-router-dom'
import { t } from '../locales/t'
import { ApiError } from '../api/client'
import { ROUTE_PATTERNS } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import {
  GOAL_ID,
  makeDashboard,
  makeGoal,
  makeGoalCard,
  makeGoalStats,
  makeTodayQuotaEntry,
  makeWeeklyDigest,
} from '../test/fixtures'
import { DashboardPage } from './DashboardPage'

const getDashboard = vi.hoisted(() => vi.fn())
vi.mock('../api/dashboard', () => ({ getDashboard }))

const listGoals = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({ listGoals }))

// 今日の一言は独立した非同期クエリ。本テストの対象ではないため固定値を返す。
const getDailyMessage = vi.hoisted(() => vi.fn())
vi.mock('../api/records', () => ({ getDailyMessage }))

// 直近4週間カレンダー（S-4 4-5）も独立した非同期クエリ。本テストの対象ではないため
// 固定値を返す（描画自体はRecentActivityCalendarSection.test.tsxが検証する）。
const getCalendar = vi.hoisted(() => vi.fn())
vi.mock('../api/calendar', () => ({ getCalendar }))

const OTHER_GOAL_ID = GOAL_ID + 1
const OTHER_MATERIAL_NAME = '別目標の教材'
const WELCOME_MARKER = 'welcome-marker'

/** `/welcome`へのリダイレクトを検証するためのルータ込みの描画
 * （ProgressOnlyPage.test.tsxと同じ、実際のルートへ遷移したかをマーカー要素の
 * 出現で確かめる方式）。 */
function renderDashboardWithRouter(initialEntries: InitialEntry[]) {
  return renderWithProviders(
    <Routes>
      <Route path={ROUTE_PATTERNS.dashboard} element={<DashboardPage />} />
      <Route path={ROUTE_PATTERNS.welcome} element={<p>{WELCOME_MARKER}</p>} />
    </Routes>,
    { initialEntries },
  )
}

/** 2目標が同時進行し、それぞれのカード・統計・ノルマが返っている状態。 */
function twoActiveGoals() {
  listGoals.mockResolvedValue([
    makeGoal(),
    makeGoal({ id: OTHER_GOAL_ID, name: '目標B' }),
  ])
  getDashboard.mockResolvedValue(
    makeDashboard({
      goal_cards: [
        makeGoalCard(),
        makeGoalCard({ goal_id: OTHER_GOAL_ID, goal_name: '目標B' }),
      ],
      goal_stats: [
        makeGoalStats(),
        makeGoalStats({ goal_id: OTHER_GOAL_ID, goal_name: '目標B' }),
      ],
      today_quota: [
        makeTodayQuotaEntry(),
        makeTodayQuotaEntry({
          goal_id: OTHER_GOAL_ID,
          goal_name: '目標B',
          material_name: OTHER_MATERIAL_NAME,
        }),
      ],
      weekly_digests: [
        makeWeeklyDigest({ ai_summary_text: '目標Aの先週のまとめ' }),
        makeWeeklyDigest({
          goal_id: OTHER_GOAL_ID,
          goal_name: '目標B',
          ai_summary_text: '目標Bの先週のまとめ',
        }),
      ],
    }),
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getDashboard.mockResolvedValue(makeDashboard())
  listGoals.mockResolvedValue([makeGoal()])
  getDailyMessage.mockResolvedValue(null)
  getCalendar.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
})

describe('DashboardPage の読み込みとエラー', () => {
  it('shows the loading text until both requests settle', () => {
    getDashboard.mockReturnValue(new Promise(() => undefined))
    renderWithProviders(<DashboardPage />)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows the localized message when the dashboard request fails', async () => {
    getDashboard.mockRejectedValue(new ApiError('VALIDATION_ERROR', 'サーバ側の文言'))
    renderWithProviders(<DashboardPage />)

    expect(await screen.findByText(t('errors.VALIDATION_ERROR'))).toBeDefined()
  })

  it('shows an error when only the goal list fails, instead of an empty screen', async () => {
    // 目標一覧が取れないと対象目標を決められず、全セクションが空表示になってしまう。
    listGoals.mockRejectedValue(new ApiError('VALIDATION_ERROR', 'サーバ側の文言'))
    renderWithProviders(<DashboardPage />)

    expect(await screen.findByText(t('errors.VALIDATION_ERROR'))).toBeDefined()
  })

  it('falls back to the default message for a failure that is not an ApiError', async () => {
    getDashboard.mockRejectedValue(new Error('boom'))
    renderWithProviders(<DashboardPage />)

    expect(await screen.findByText(t('errors.default'))).toBeDefined()
  })
})

describe('DashboardPage の目標の絞り込み', () => {
  it('hides the goal selector while only one goal is running', async () => {
    renderWithProviders(<DashboardPage />)

    await screen.findByText(t('dashboard.title'))
    expect(screen.queryByRole('button', { name: /目標B/ })).toBeNull()
  })

  it('shows only the selected goal and switches everything together', async () => {
    const user = userEvent.setup()
    twoActiveGoals()
    renderWithProviders(<DashboardPage />)

    // 初期表示は先頭の目標。別目標のノルマ・先週のまとめは混ざらない。
    expect(await screen.findByText('教材A')).toBeDefined()
    expect(screen.queryByText(OTHER_MATERIAL_NAME)).toBeNull()
    expect(screen.getByText('目標Aの先週のまとめ')).toBeDefined()
    expect(screen.queryByText('目標Bの先週のまとめ')).toBeNull()

    await user.click(screen.getByRole('button', { name: /目標B/ }))

    await waitFor(() => expect(screen.getByText(OTHER_MATERIAL_NAME)).toBeDefined())
    expect(screen.queryByText('教材A')).toBeNull()
    expect(screen.getByText('目標Bの先週のまとめ')).toBeDefined()
    expect(screen.queryByText('目標Aの先週のまとめ')).toBeNull()
  })

  it('keeps the goal independent state visible whichever goal is selected', async () => {
    const user = userEvent.setup()
    twoActiveGoals()
    renderWithProviders(<DashboardPage />)

    // 本日の状態はアプリ全体の値であり、目標の切り替えで消えてはいけない。
    // ラベルと値は同じ要素に「本日の状態：未報告」と続けて描かれるため部分一致で探す。
    const statusText = new RegExp(t('dashboard.todayStatus.label'))
    expect(await screen.findByText(statusText)).toBeDefined()

    await user.click(screen.getByRole('button', { name: /目標B/ }))

    expect(screen.getByText(statusText)).toBeDefined()
  })
})

describe('DashboardPage のウェルカム画面誘導', () => {
  it('redirects to /welcome when there are no goals', async () => {
    listGoals.mockResolvedValue([])
    renderDashboardWithRouter([ROUTE_PATTERNS.dashboard])

    expect(await screen.findByText(WELCOME_MARKER)).toBeDefined()
  })

  it('does not redirect while at least one goal exists', async () => {
    renderDashboardWithRouter([ROUTE_PATTERNS.dashboard])

    await screen.findByText(t('dashboard.title'))
    expect(screen.queryByText(WELCOME_MARKER)).toBeNull()
  })
})

describe('DashboardPage のAI未設定時のフォールバック（S-4 4-6）', () => {
  // AI未設定時にAI依存の各セクションが崩れず、非AIのフォールバック表示へ切り替わる
  // ことを確かめる（4-1: 今日の一言、4-4: 先週のまとめ）。直近4週間カレンダー（4-5）は
  // AIに一切依存しない機能のため、この状態でも通常どおり表示され続けることを併せて示す。
  it('shows the fixed daily-message text and the non-AI weekly digest instead of AI content', async () => {
    getDailyMessage.mockResolvedValue([
      {
        target_date: '2026-09-13',
        goal_id: GOAL_ID,
        goal_name: '目標A',
        body: '',
        generated_at: '2026-09-13T00:00:00',
        is_fallback: true,
      },
    ])
    getDashboard.mockResolvedValue(
      makeDashboard({
        weekly_digests: [
          makeWeeklyDigest({ ai_summary_text: null, recorded_days: 2, total_minutes: 60 }),
        ],
      }),
    )
    renderWithProviders(<DashboardPage />)

    expect(await screen.findByText(t('dashboard.todayMessage.fallback'))).toBeDefined()
    expect(
      screen.getByText(t('dashboard.weeklyDigest.recordedDays', { days: 2 }), { exact: false }),
    ).toBeDefined()
    // 直近4週間カレンダーはAIに依存しないため、この状態でも通常どおり表示される。
    expect(screen.getByText(t('dashboard.recentActivityCalendar.title'))).toBeDefined()
  })
})

describe('DashboardPage の初回記録バナー', () => {
  // location.stateのような遷移1回限りの状態ではなく、実データ（has_ever_reported_record、
  // S-4 4-2）で判定するため、リロードやブラウザバックをまたいでも表示が保たれる。

  it('shows the banner when a goal is active but no record has ever been reported', async () => {
    getDashboard.mockResolvedValue(makeDashboard({ has_ever_reported_record: false }))
    renderWithProviders(<DashboardPage />)

    expect(await screen.findByText(t('dashboard.firstRecordBanner'))).toBeDefined()
  })

  it('hides the banner once any record has ever been reported', async () => {
    getDashboard.mockResolvedValue(makeDashboard({ has_ever_reported_record: true }))
    renderWithProviders(<DashboardPage />)

    await screen.findByText(t('dashboard.title'))
    expect(screen.queryByText(t('dashboard.firstRecordBanner'))).toBeNull()
  })

  it('hides the banner while there are no active goals yet', async () => {
    getDashboard.mockResolvedValue(
      makeDashboard({ has_ever_reported_record: false, goal_cards: [], goal_stats: [], today_quota: [] }),
    )
    renderWithProviders(<DashboardPage />)

    await screen.findByText(t('dashboard.title'))
    expect(screen.queryByText(t('dashboard.firstRecordBanner'))).toBeNull()
  })
})
