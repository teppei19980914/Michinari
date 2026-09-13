/** 目標カードの、種別ごとの表示内容を固定する（Phase 35）。
 *
 * 資格試験は計画管理の指標（進捗率・残日数・完了予測日との乖離）を、読書と仕事は
 * 記録の継続を示す指標（残日数／経過日数・直近記録日・連続記録日数）を出す。読書・仕事に
 * 進捗率や完了予測を出すと、ノルマのない目標に達成度があるかのように見えてしまう
 * （要件定義書R-71・R-74）。種別の取り違えは数字が並んでいる分だけ気づきにくいため固定する。
 *
 * 算出できない値は「—」等のフォールバック文言へ落ちる。0と未算出の取り違えを防ぐために
 * それぞれ確かめる。 */
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeBook, makeGoalCard, makeWorkAssignment } from '../../test/fixtures'
import { GoalCardList } from './GoalCardList'

afterEach(() => {
  cleanup()
})

describe('GoalCardList', () => {
  it('renders nothing when there is no goal', () => {
    const { container } = renderWithProviders(<GoalCardList goalCards={[]} />)

    expect(container.textContent).toBe('')
  })

  it('links each card to the goal detail screen', () => {
    renderWithProviders(<GoalCardList goalCards={[makeGoalCard()]} />)

    expect(screen.getByRole('link').getAttribute('href')).toBe(ROUTES.goalDetail(GOAL_ID))
  })
})

describe('GoalCardList（資格試験）', () => {
  it('shows the planning figures', () => {
    renderWithProviders(
      <GoalCardList
        goalCards={[makeGoalCard({ progress_rate: 0.42, remaining_days: 80, forecast_deviation_days: 3.4 })]}
      />,
    )

    expect(screen.getByText(t('dashboard.goalCard.progressRate'))).toBeDefined()
    expect(screen.getByText(t('dashboard.goalCard.remainingDays', { days: 80 }))).toBeDefined()
    // 乖離日数は四捨五入した整数で示す。
    expect(
      screen.getByText(t('dashboard.goalCard.forecastDeviation', { days: 3 })),
    ).toBeDefined()
  })

  it('falls back for every figure that could not be computed', () => {
    renderWithProviders(
      <GoalCardList
        goalCards={[
          makeGoalCard({ progress_rate: null, remaining_days: null, forecast_deviation_days: null }),
        ]}
      />,
    )

    expect(screen.getByText(t('dashboard.goalCard.notAvailable'))).toBeDefined()
    expect(screen.getByText(t('dashboard.goalCard.remainingDaysUnavailable'))).toBeDefined()
    expect(screen.getByText(t('dashboard.goalCard.forecastDeviationUnavailable'))).toBeDefined()
  })
})

describe('GoalCardList（読書）', () => {
  const readingCard = (bookOverrides = {}, cardOverrides = {}) =>
    makeGoalCard({ category: 'READING', book: makeBook(bookOverrides), ...cardOverrides })

  it('shows the reading figures instead of the planning ones', () => {
    renderWithProviders(<GoalCardList goalCards={[readingCard()]} />)

    expect(
      screen.getByText(t('dashboard.goalCard.remainingDaysReading', { days: 80 })),
    ).toBeDefined()
    expect(screen.getByText(t('dashboard.goalCard.currentStreak', { days: 3 }))).toBeDefined()
    // ノルマのない目標に完了予測を出さない。
    expect(screen.queryByText(t('dashboard.goalCard.progressRate'))).toBeNull()
    expect(screen.queryByText(new RegExp(t('dashboard.goalCard.forecastDeviation', { days: 0 })))).toBeNull()
  })

  it('falls back when the book has never been read', () => {
    renderWithProviders(<GoalCardList goalCards={[readingCard({ last_reading_date: null })]} />)

    expect(screen.getByText(t('dashboard.goalCard.lastReadingDateUnavailable'))).toBeDefined()
  })

  it('hides the page progress until it can be computed', () => {
    const { unmount } = renderWithProviders(<GoalCardList goalCards={[readingCard()]} />)
    expect(screen.getByText(t('dashboard.goalCard.pageProgress'))).toBeDefined()

    unmount()
    renderWithProviders(<GoalCardList goalCards={[readingCard({ progress_rate: null })]} />)

    expect(screen.queryByText(t('dashboard.goalCard.pageProgress'))).toBeNull()
  })

  it('shows only the remaining days when the book is not registered yet', () => {
    renderWithProviders(
      <GoalCardList goalCards={[makeGoalCard({ category: 'READING', book: null })]} />,
    )

    expect(
      screen.getByText(t('dashboard.goalCard.remainingDaysReading', { days: 80 })),
    ).toBeDefined()
    expect(screen.queryByText(t('dashboard.goalCard.pageProgress'))).toBeNull()
  })

  it('falls back when the reading deadline is unknown', () => {
    renderWithProviders(<GoalCardList goalCards={[readingCard({}, { remaining_days: null })]} />)

    expect(screen.getByText(t('dashboard.goalCard.remainingDaysUnavailable'))).toBeDefined()
  })
})

describe('GoalCardList（仕事）', () => {
  const workCard = (assignmentOverrides = {}) =>
    makeGoalCard({ category: 'WORK', work_assignment: makeWorkAssignment(assignmentOverrides) })

  it('shows the work figures instead of the planning ones', () => {
    renderWithProviders(<GoalCardList goalCards={[workCard()]} />)

    expect(screen.getByText(t('dashboard.goalCard.elapsedDays', { days: 12 }))).toBeDefined()
    expect(screen.getByText(t('dashboard.goalCard.currentStreakWork', { days: 3 }))).toBeDefined()
    expect(screen.getByText(t('dashboard.goalCard.hasRecentMonthlyReport'))).toBeDefined()
    expect(screen.queryByText(t('dashboard.goalCard.progressRate'))).toBeNull()
  })

  it('points out that the monthly report is missing', () => {
    renderWithProviders(<GoalCardList goalCards={[workCard({ has_recent_monthly_report: false })]} />)

    expect(screen.getByText(t('dashboard.goalCard.hasRecentMonthlyReportNone'))).toBeDefined()
  })

  it('falls back when the assignment has never been worked on', () => {
    renderWithProviders(<GoalCardList goalCards={[workCard({ last_work_date: null })]} />)

    expect(screen.getByText(t('dashboard.goalCard.lastWorkDateUnavailable'))).toBeDefined()
  })

  it('shows only the goal name when the assignment is not registered yet', () => {
    renderWithProviders(
      <GoalCardList goalCards={[makeGoalCard({ category: 'WORK', work_assignment: null })]} />,
    )

    expect(screen.getByRole('heading', { name: '目標A' })).toBeDefined()
    expect(screen.queryByText(new RegExp(t('dashboard.goalCard.elapsedDays', { days: 12 })))).toBeNull()
  })
})
