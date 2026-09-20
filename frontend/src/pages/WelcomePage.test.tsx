/** ウェルカム画面の3カードからの遷移を固定する。初回記録バナー（S-4 4-2）は
 * ダッシュボード側が実データ（has_ever_reported_record）で判定するため、
 * ここでは遷移先がダッシュボードであることのみを確かめる。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { t } from '../locales/t'
import { ROUTE_PATTERNS } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { makeGoal } from '../test/fixtures'
import { WelcomePage } from './WelcomePage'

const createGoal = vi.hoisted(() => vi.fn())
const createBook = vi.hoisted(() => vi.fn())
const createWorkAssignment = vi.hoisted(() => vi.fn())
const activateGoal = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({ createGoal, createBook, createWorkAssignment, activateGoal }))

const getToday = vi.hoisted(() => vi.fn())
vi.mock('../api/records', () => ({ getToday }))

const EXAM_WIZARD_MARKER = 'exam-wizard-marker'
const CREATED_GOAL = makeGoal({ id: 7 })

function DashboardMarker() {
  return <p>dashboard-marker</p>
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path={ROUTE_PATTERNS.welcome} element={<WelcomePage />} />
      <Route path={ROUTE_PATTERNS.dashboard} element={<DashboardMarker />} />
      <Route path={ROUTE_PATTERNS.goalNewExam} element={<p>{EXAM_WIZARD_MARKER}</p>} />
    </Routes>,
    { initialEntries: [ROUTE_PATTERNS.welcome] },
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getToday.mockResolvedValue({ logical_date: '2026-05-01' })
  createGoal.mockResolvedValue(CREATED_GOAL)
  createBook.mockResolvedValue({})
  createWorkAssignment.mockResolvedValue({})
  activateGoal.mockResolvedValue(CREATED_GOAL)
})

afterEach(() => {
  cleanup()
})

describe('WelcomePage の表示', () => {
  it('shows the app intro and the three category cards', () => {
    renderPage()

    expect(screen.getByText(t('welcome.appIntro'))).toBeDefined()
    expect(screen.getByText(t('welcome.reading.title'))).toBeDefined()
    expect(screen.getByText(t('welcome.work.title'))).toBeDefined()
    expect(screen.getByText(t('welcome.exam.title'))).toBeDefined()
    expect(screen.getByText(t('welcome.exam.note'))).toBeDefined()
  })
})

describe('WelcomePage からの遷移', () => {
  it('navigates to the exam wizard when the exam card is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByText(t('welcome.exam.title')))

    expect(await screen.findByText(EXAM_WIZARD_MARKER)).toBeDefined()
  })

  it('navigates to the dashboard when "later" is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: t('welcome.later') }))

    expect(await screen.findByText('dashboard-marker')).toBeDefined()
  })

  it('navigates to the dashboard when the reading quick-create form succeeds', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByText(t('welcome.reading.title')))
    await waitFor(() => expect(getToday).toHaveBeenCalled())
    await user.type(screen.getByLabelText(t('goals.new.quickCreate.reading.titleLabel')), '銀河鉄道の夜')
    await user.click(screen.getByRole('button', { name: t('goals.new.quickCreate.submitButton') }))

    expect(await screen.findByText('dashboard-marker')).toBeDefined()
    expect(createBook).toHaveBeenCalledOnce()
  })

  it('opens the work quick-create form', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByText(t('welcome.work.title')))

    expect(screen.getByLabelText(t('goals.new.quickCreate.work.nameLabel'))).toBeDefined()
  })

  it('does not leak input typed for one category into the form for another', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByText(t('welcome.reading.title')))
    await user.type(screen.getByLabelText(t('goals.new.quickCreate.reading.titleLabel')), '銀河鉄道の夜')
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    await user.click(screen.getByText(t('welcome.work.title')))

    expect(screen.getByLabelText<HTMLInputElement>(t('goals.new.quickCreate.work.nameLabel')).value).toBe('')
  })
})
