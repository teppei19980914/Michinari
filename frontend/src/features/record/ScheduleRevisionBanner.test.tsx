/** 日次報告の確定後の案内の出し分けを固定する（開発Todo_スケジュール・ガントチャート_v1.1
 * 13.1・13.8、単位5）。 */
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID } from '../../test/fixtures'
import { ScheduleRevisionBanner } from './ScheduleRevisionBanner'

afterEach(() => {
  cleanup()
})

describe('ScheduleRevisionBanner', () => {
  it('renders nothing when there is no status (not a candidate goal)', () => {
    const { container } = renderWithProviders(
      <ScheduleRevisionBanner goalId={GOAL_ID} status={undefined} />,
    )
    expect(container.textContent).toBe('')
  })

  it('renders nothing when no revision was needed', () => {
    const { container } = renderWithProviders(
      <ScheduleRevisionBanner goalId={GOAL_ID} status="no_proposal" />,
    )
    expect(container.textContent).toBe('')
  })

  it('shows the generating message', () => {
    renderWithProviders(<ScheduleRevisionBanner goalId={GOAL_ID} status="generating" />)
    expect(screen.getByText(t('dailyReport.scheduleRevision.generating'))).not.toBe(null)
  })

  it('shows the failure message', () => {
    renderWithProviders(<ScheduleRevisionBanner goalId={GOAL_ID} status="failed" />)
    expect(screen.getByText(t('dailyReport.scheduleRevision.failed'))).not.toBe(null)
  })

  it('links to the schedule tab when a proposal was created', () => {
    renderWithProviders(<ScheduleRevisionBanner goalId={GOAL_ID} status="succeeded" />)
    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe(ROUTES.goalScheduleTab(GOAL_ID))
    expect(link.textContent).toContain(t('dailyReport.scheduleRevision.succeeded'))
  })
})
