/** スケジュールの修正案の案内バナーの出し分けを固定する（開発Todo_スケジュール・
 * ガントチャート_v1.1 13.8、単位5）。`WarningBanner.test.tsx`と同じ方針。 */
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeGoalCard } from '../../test/fixtures'
import { ScheduleRevisionBanner } from './ScheduleRevisionBanner'

afterEach(() => {
  cleanup()
})

describe('ScheduleRevisionBanner', () => {
  it('renders nothing while no goal has a pending proposal', () => {
    const { container } = renderWithProviders(
      <ScheduleRevisionBanner goalCards={[makeGoalCard()]} />,
    )

    expect(container.textContent).toBe('')
  })

  it('links a goal with a pending proposal to its schedule tab', () => {
    renderWithProviders(
      <ScheduleRevisionBanner
        goalCards={[makeGoalCard({ has_pending_schedule_revision: true })]}
      />,
    )

    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe(ROUTES.goalScheduleTab(GOAL_ID))
    expect(link.textContent).toContain(t('dashboard.scheduleRevisionBanner.message'))
  })

  it('lists every goal with a pending proposal and leaves the others out', () => {
    renderWithProviders(
      <ScheduleRevisionBanner
        goalCards={[
          makeGoalCard({ has_pending_schedule_revision: true }),
          makeGoalCard({ goal_id: GOAL_ID + 1, goal_name: '目標B' }),
          makeGoalCard({
            goal_id: GOAL_ID + 2,
            goal_name: '目標C',
            has_pending_schedule_revision: true,
          }),
        ]}
      />,
    )

    expect(screen.getAllByRole('link')).toHaveLength(2)
    expect(screen.queryByText(/目標B/)).toBeNull()
  })
})
