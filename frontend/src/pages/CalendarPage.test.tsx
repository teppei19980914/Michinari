/** SC-05 カレンダー（CalendarPage）の月移動・日付選択時の遷移先・補助表示の対象目標を
 * 固定する回帰テスト（Phase 36）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で日付選択の処理と
 * 選択モーダルを切り出すにあたり、先に現状の振る舞いを固定しておくための安全網である。
 *
 * 日付を押したときの遷移先は状態によって6通りに分かれる。取り違えても「どこかの画面が
 * 開く」だけなので画面を見ても気づけず、2日以上前の日で日次報告へ送ると確定時に弾かれて
 * 入力内容が失われる（仕様書1.1（改20）で解消した不具合の再発にあたる）。
 *
 * 遷移先の判定そのものは resolveCalendarDateAction.test.ts が担うため、ここでは
 * 「判定の結果としてどの画面へ進むか・どのモーダルが開くか」に絞る。
 *
 * カバレッジの扱いは他の画面テストと同じ（vite.config.ts の coverage.exclude で
 * `src/pages/**\/*.tsx` を除外し、振る舞いはこのテストが守る）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { GOAL_ID, makeGoal, makeGoalDetail, makeSubject } from '../test/fixtures'
import type { CalendarDayRead } from '../api/calendar'
import { CalendarPage } from './CalendarPage'

const getCalendar = vi.hoisted(() => vi.fn())
vi.mock('../api/calendar', () => ({ getCalendar, updateDayType: vi.fn() }))

const getToday = vi.hoisted(() => vi.fn())
vi.mock('../api/records', () => ({ getToday }))

const listGoals = vi.hoisted(() => vi.fn())
const getGoal = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({ listGoals, getGoal }))

const navigate = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}))

/** 当日。テストは実時間の「今月」を描画するため、日付は当月内へ寄せて組み立てる。 */
const TODAY = new Date()
const toIso = (date: Date) => date.toISOString().slice(0, 10)
/** 当月の日。月境界に依存しないよう、当月の10日・11日・12日を使う。 */
const dayOfThisMonth = (dayOfMonth: number) =>
  toIso(new Date(Date.UTC(TODAY.getFullYear(), TODAY.getMonth(), dayOfMonth)))

const TODAY_DATE = dayOfThisMonth(12)
const YESTERDAY_DATE = dayOfThisMonth(11)
const OLD_DATE = dayOfThisMonth(10)
const FUTURE_DATE = dayOfThisMonth(20)

const SECOND_GOAL_ID = GOAL_ID + 1
const FIRST_GOAL_NAME = '目標A'
const SECOND_GOAL_NAME = '目標B'

function makeDay(targetDate: string, overrides: Partial<CalendarDayRead> = {}): CalendarDayRead {
  return { target_date: targetDate, day_type: 'PLAN', record_state: null, ...overrides }
}

/** 当月のグリッドに載る日をひととおり用意する（押した日の情報が無いと判定が変わるため）。 */
function makeCalendar(overrides: Partial<Record<string, Partial<CalendarDayRead>>> = {}) {
  return [OLD_DATE, YESTERDAY_DATE, TODAY_DATE, FUTURE_DATE].map((date) =>
    makeDay(date, overrides[date] ?? {}),
  )
}

/** 日付セル内の日付ボタン（「日種別」リンクと区別するため、数字そのもので引く）。 */
function dayButton(isoDate: string) {
  const dayOfMonth = String(Number(isoDate.slice(8, 10)))
  return screen
    .getAllByRole('button', { name: dayOfMonth })
    .find((button) => button.className.includes('font-medium')) as HTMLElement
}

async function renderPage({
  calendar = makeCalendar(),
  goals = [makeGoal({ name: FIRST_GOAL_NAME })],
} = {}) {
  getToday.mockResolvedValue({ logical_date: TODAY_DATE })
  getCalendar.mockResolvedValue(calendar)
  listGoals.mockResolvedValue(goals)
  const result = renderWithProviders(<CalendarPage />)
  await screen.findByText(t('calendar.title'))
  return result
}

beforeEach(() => {
  vi.clearAllMocks()
  getGoal.mockResolvedValue(makeGoalDetail())
})

afterEach(() => {
  cleanup()
})

describe('CalendarPage の読み込み', () => {
  it('shows the loading text until every query settles', () => {
    getToday.mockReturnValue(new Promise(() => undefined))
    getCalendar.mockResolvedValue([])
    listGoals.mockResolvedValue([])
    renderWithProviders(<CalendarPage />)
    expect(screen.getByText(t('common.loading'))).toBeTruthy()
  })

  it('shows an error when the calendar cannot be read', async () => {
    getToday.mockResolvedValue({ logical_date: TODAY_DATE })
    getCalendar.mockRejectedValue(new Error('boom'))
    listGoals.mockResolvedValue([])
    renderWithProviders(<CalendarPage />)
    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
  })

  it('shows an error when the goal list cannot be read', async () => {
    // 目標が取れないと補助表示が常に空になるため、他の必須クエリと同様にエラーにする。
    getToday.mockResolvedValue({ logical_date: TODAY_DATE })
    getCalendar.mockResolvedValue(makeCalendar())
    listGoals.mockRejectedValue(new Error('boom'))
    renderWithProviders(<CalendarPage />)
    expect(await screen.findByText(t('errors.default'))).toBeTruthy()
  })
})

describe('CalendarPage の月移動', () => {
  it('starts on the current month and steps back and forward', async () => {
    const user = userEvent.setup()
    await renderPage()
    const currentMonth = `${TODAY.getFullYear()}-${String(TODAY.getMonth() + 1).padStart(2, '0')}`
    expect(screen.getByText(currentMonth)).toBeTruthy()

    await user.click(screen.getByRole('button', { name: t('calendar.prevMonth') }))
    expect(screen.queryByText(currentMonth)).toBe(null)

    await user.click(screen.getByRole('button', { name: t('calendar.nextMonth') }))
    expect(screen.getByText(currentMonth)).toBeTruthy()
  })
})

describe('CalendarPage の日付選択', () => {
  it('opens the daily report for today', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(dayButton(TODAY_DATE))
    expect(navigate).toHaveBeenCalledWith(ROUTES.dailyReport(TODAY_DATE))
  })

  it('asks which kind of record to add for an empty yesterday', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(dayButton(YESTERDAY_DATE))

    // 未入力の前日は日次報告と進捗のみ登録の選択肢を出す（遷移はしない）。
    expect(navigate).not.toHaveBeenCalled()
    expect(screen.getByText(t('calendar.choiceModal.title'))).toBeTruthy()
    expect(screen.getByText(YESTERDAY_DATE)).toBeTruthy()
  })

  it('promotes a yesterday that already has a progress-only record', async () => {
    const user = userEvent.setup()
    await renderPage({
      calendar: makeCalendar({ [YESTERDAY_DATE]: { record_state: 'PROGRESS_ONLY' } }),
    })
    await user.click(dayButton(YESTERDAY_DATE))
    expect(navigate).toHaveBeenCalledWith(ROUTES.dailyReport(YESTERDAY_DATE))
  })

  it('sends an older empty day to the progress-only screen', async () => {
    // 2日以上前は確定できないため、日次報告へ送ると入力内容が失われる。
    const user = userEvent.setup()
    await renderPage()
    await user.click(dayButton(OLD_DATE))
    expect(navigate).toHaveBeenCalledWith(ROUTES.dailyReportProgress(OLD_DATE))
  })

  it('sends an older recorded day to the view screen', async () => {
    const user = userEvent.setup()
    await renderPage({ calendar: makeCalendar({ [OLD_DATE]: { record_state: 'REPORTED' } }) })
    await user.click(dayButton(OLD_DATE))
    expect(navigate).toHaveBeenCalledWith(ROUTES.dailyReportView(OLD_DATE))
  })

  it('only offers editing the day type for a future day', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(dayButton(FUTURE_DATE))

    expect(navigate).not.toHaveBeenCalled()
    expect(screen.getByText(t('calendar.dayTypeModal.title'))).toBeTruthy()
  })

  it('opens the day type editor from the per-cell link', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(screen.getAllByRole('button', { name: t('calendar.editDayTypeLink') })[0])
    expect(screen.getByText(t('calendar.dayTypeModal.title'))).toBeTruthy()
  })
})

describe('CalendarPage の選択モーダル', () => {
  it('links to both the daily report and the progress-only screen', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(dayButton(YESTERDAY_DATE))

    const report = screen.getByRole('button', { name: t('calendar.choiceModal.report') })
    const progressOnly = screen.getByRole('button', {
      name: t('calendar.choiceModal.progressOnly'),
    })
    expect(report.closest('a')?.getAttribute('href')).toBe(ROUTES.dailyReport(YESTERDAY_DATE))
    expect(progressOnly.closest('a')?.getAttribute('href')).toBe(
      ROUTES.dailyReportProgress(YESTERDAY_DATE),
    )
  })

  it('closes the choice modal once a choice is made', async () => {
    const user = userEvent.setup()
    await renderPage()
    await user.click(dayButton(YESTERDAY_DATE))
    await user.click(screen.getByRole('button', { name: t('calendar.choiceModal.report') }))

    await waitFor(() => expect(screen.queryByText(t('calendar.choiceModal.title'))).toBe(null))
  })
})

describe('CalendarPage の目標タブと補助表示', () => {
  it('hides the goal tab bar while only one goal is active', async () => {
    await renderPage()
    expect(screen.queryByRole('button', { name: new RegExp(FIRST_GOAL_NAME) })).toBe(null)
  })

  it('shows the auxiliary markers of the selected goal only', async () => {
    // 補助表示は選択中の1目標分のみ（Phase25。旧仕様6.4の全目標集約表示を改訂）。
    const user = userEvent.setup()
    getGoal.mockImplementation((goalId: number) =>
      Promise.resolve(
        goalId === GOAL_ID
          ? makeGoalDetail({
              name: FIRST_GOAL_NAME,
              exam_subjects: [makeSubject({ exam_date_fixed: TODAY_DATE })],
            })
          : makeGoalDetail({
              id: SECOND_GOAL_ID,
              name: SECOND_GOAL_NAME,
              exam_subjects: [makeSubject({ id: 99, exam_date_fixed: FUTURE_DATE })],
            }),
      ),
    )
    await renderPage({
      goals: [
        makeGoal({ name: FIRST_GOAL_NAME }),
        makeGoal({ id: SECOND_GOAL_ID, name: SECOND_GOAL_NAME }),
      ],
    })

    const examDateLabel = t('calendar.auxiliaryMarker.EXAM_DATE')
    await screen.findByText(new RegExp(examDateLabel))
    // 最初の目標の受験日（当日）にだけマーカーが出る。
    expect(screen.getAllByText(new RegExp(examDateLabel)).length).toBe(1)

    await user.click(screen.getByRole('button', { name: new RegExp(SECOND_GOAL_NAME) }))
    await waitFor(() => expect(getGoal).toHaveBeenCalledWith(SECOND_GOAL_ID))
  })

  it('lists several markers of one day in a fixed order', async () => {
    // 受験日と負荷調整が同じ日に重なる場合、表示順は種別で固定する（日によって
    // 並びが変わると、同じ画面なのに違うものに見える）。
    getGoal.mockResolvedValue(
      makeGoalDetail({
        name: FIRST_GOAL_NAME,
        exam_subjects: [makeSubject({ exam_date_fixed: TODAY_DATE })],
        load_profiles: [
          { id: 1, goal_id: GOAL_ID, date_from: TODAY_DATE, date_to: TODAY_DATE, coefficient: 1.5, note: null },
        ],
      }),
    )
    await renderPage()

    const examDateLabel = t('calendar.auxiliaryMarker.EXAM_DATE')
    const loadAdjustedLabel = t('calendar.auxiliaryMarker.LOAD_ADJUSTED')
    const cell = await screen.findByText(new RegExp(examDateLabel))
    expect(cell.textContent).toBe(`${examDateLabel} / ${loadAdjustedLabel}`)
  })

  it('lets the user switch the goal used for the auxiliary markers', async () => {
    await renderPage({
      goals: [
        makeGoal({ name: FIRST_GOAL_NAME }),
        makeGoal({ id: SECOND_GOAL_ID, name: SECOND_GOAL_NAME }),
      ],
    })
    const tabBar = screen.getByRole('button', { name: new RegExp(FIRST_GOAL_NAME) })
    expect(within(tabBar.parentElement as HTMLElement).getAllByRole('button').length).toBe(2)
  })
})
