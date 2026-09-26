/** 書籍詳細（SC-19）の振る舞いを固定する。想起記録・成長記述・振り返りレポートは
 * 既存コンポーネントをそのまま流用するため、ここでは配線（どのタブでどれが出るか・
 * READING以外/book無しのフォールバック・本棚へ戻るリンク）だけを確かめ、各タブの
 * 内部実装はそれぞれの既存テストに委ねる（vi.mockで差し替える）。 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { renderWithProviders } from '../test/renderWithProviders'
import { GOAL_ID, makeGoalDetail, makeBook } from '../test/fixtures'
import { BookDetailPage } from './BookDetailPage'

const getGoal = vi.hoisted(() => vi.fn())
const listGoals = vi.hoisted(() => vi.fn())
vi.mock('../api/goals', () => ({ getGoal, listGoals }))

vi.mock('../features/analytics/ReadingLogHistoryTab', () => ({
  ReadingLogHistoryTab: ({ goalId }: { goalId: number }) => (
    <div>ReadingLogHistoryTab:{goalId}</div>
  ),
}))
vi.mock('../features/analytics/GrowthDescriptionTab', () => ({
  GrowthDescriptionTab: ({ goalId }: { goalId: number }) => (
    <div>GrowthDescriptionTab:{goalId}</div>
  ),
}))
vi.mock('../features/export/RetrospectiveSection', () => ({
  RetrospectiveSection: ({ goalId }: { goalId: number }) => (
    <div>RetrospectiveSection:{goalId}</div>
  ),
}))

// URLから書籍(目標)IDを読むため、ルートパラメータを固定する（GoalDetailPage.test.tsxと同じ方針）。
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useParams: () => ({ goalId: String(GOAL_ID) }),
}))

function renderPage() {
  return renderWithProviders(<BookDetailPage />)
}

afterEach(() => {
  cleanup()
})

describe('BookDetailPage', () => {
  it('shows the fallback message for a non-reading goal', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ category: 'EXAM', book: null }))
    listGoals.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText(t('bookshelf.detail.notReadingGoal'))).toBeDefined()
  })

  it('shows the fallback message when the goal has no book', async () => {
    getGoal.mockResolvedValue(makeGoalDetail({ category: 'READING', book: null }))
    listGoals.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText(t('bookshelf.detail.notReadingGoal'))).toBeDefined()
  })

  it('shows the book info tab by default and links back to the bookshelf', async () => {
    getGoal.mockResolvedValue(
      makeGoalDetail({
        category: 'READING',
        status: 'CLOSED_WITH_RESULT',
        book: makeBook({ title: '銀河鉄道の夜' }),
      }),
    )
    listGoals.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText('銀河鉄道の夜')).toBeDefined()
    const backLink = screen.getByText(t('bookshelf.detail.backLink')).closest('a') as HTMLAnchorElement
    expect(backLink.getAttribute('href')).toBe(ROUTES.bookshelf)
  })

  it('switches to the reading log tab', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(
      makeGoalDetail({ category: 'READING', status: 'CLOSED_WITH_RESULT', book: makeBook() }),
    )
    listGoals.mockResolvedValue([])
    renderPage()

    await user.click(await screen.findByRole('button', { name: t('bookshelf.detail.tabs.log') }))

    expect(screen.getByText(`ReadingLogHistoryTab:${GOAL_ID}`)).toBeDefined()
  })

  it('switches to the growth description tab', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(
      makeGoalDetail({ category: 'READING', status: 'CLOSED_WITH_RESULT', book: makeBook() }),
    )
    listGoals.mockResolvedValue([])
    renderPage()

    await user.click(
      await screen.findByRole('button', { name: t('bookshelf.detail.tabs.growth') }),
    )

    expect(screen.getByText(`GrowthDescriptionTab:${GOAL_ID}`)).toBeDefined()
  })

  it('switches to the retrospective tab', async () => {
    const user = userEvent.setup()
    getGoal.mockResolvedValue(
      makeGoalDetail({ category: 'READING', status: 'CLOSED_WITHOUT_RESULT', book: makeBook() }),
    )
    listGoals.mockResolvedValue([])
    renderPage()

    await user.click(
      await screen.findByRole('button', { name: t('bookshelf.detail.tabs.retrospective') }),
    )

    expect(screen.getByText(`RetrospectiveSection:${GOAL_ID}`)).toBeDefined()
  })
})
