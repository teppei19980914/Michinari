/** 警告バナーの出し分けを固定する（Phase 35）。
 *
 * 警告と強制リプランは利用者に取るべき行動が違う（前者は様子見でよいが、後者は計画を
 * 立て直さないと進められない）。同じ文言になっていると気づけないため、別の文言が出ることと、
 * 該当がないときは何も描かないことを固定する。 */
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeGoalCard } from '../../test/fixtures'
import { WarningBanner } from './WarningBanner'

afterEach(() => {
  cleanup()
})

describe('WarningBanner', () => {
  it('renders nothing while no goal needs attention', () => {
    const { container } = renderWithProviders(<WarningBanner goalCards={[makeGoalCard()]} />)

    expect(container.textContent).toBe('')
  })

  it('links a warning goal to its detail screen', () => {
    renderWithProviders(<WarningBanner goalCards={[makeGoalCard({ has_warning: true })]} />)

    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe(ROUTES.goalDetail(GOAL_ID))
    expect(link.textContent).toContain(t('dashboard.warningBanner.warning'))
  })

  it('distinguishes a forced replan from a plain warning', () => {
    renderWithProviders(
      <WarningBanner goalCards={[makeGoalCard({ has_forced_replan: true })]} />,
    )

    expect(screen.getByRole('link').textContent).toContain(
      t('dashboard.warningBanner.forcedReplan'),
    )
  })

  it('prefers the forced replan wording when both flags are set', () => {
    renderWithProviders(
      <WarningBanner goalCards={[makeGoalCard({ has_warning: true, has_forced_replan: true })]} />,
    )

    const text = screen.getByRole('link').textContent ?? ''
    expect(text).toContain(t('dashboard.warningBanner.forcedReplan'))
    expect(text).not.toContain(t('dashboard.warningBanner.warning'))
  })

  it('lists every goal that needs attention and leaves the healthy ones out', () => {
    renderWithProviders(
      <WarningBanner
        goalCards={[
          makeGoalCard({ has_warning: true }),
          makeGoalCard({ goal_id: GOAL_ID + 1, goal_name: '目標B' }),
          makeGoalCard({ goal_id: GOAL_ID + 2, goal_name: '目標C', has_forced_replan: true }),
        ]}
      />,
    )

    expect(screen.getAllByRole('link')).toHaveLength(2)
    expect(screen.queryByText(/目標B/)).toBeNull()
  })
})
