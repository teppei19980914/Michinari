/** 統計サマリの出し分けを固定する（Phase 35）。
 *
 * 予備日消費率は資格試験目標にしか意味がない（読書・仕事は日種別による計画運用の対象外で、
 * バックエンドも null を返す）。読書・仕事の目標に「予備日消費率: —」が並ぶと、設定し忘れの
 * ように見えてしまうため、項目ごと出さないことを固定する。
 *
 * カテゴリの判定そのものは `statsVisibility.test.ts` が担う。 */
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { GOAL_ID, makeGoalCard, makeGoalStats } from '../../test/fixtures'
import { StatsSummary } from './StatsSummary'

const WINDOW_DAYS = 14

afterEach(() => {
  cleanup()
})

describe('StatsSummary', () => {
  it('renders nothing when there is no statistics yet', () => {
    const { container } = renderWithProviders(
      <StatsSummary goalStats={[]} goalCards={[]} reportRateWindowDays={WINDOW_DAYS} />,
    )

    expect(container.textContent).toBe('')
  })

  it('shows the buffer usage rate for an exam goal', () => {
    renderWithProviders(
      <StatsSummary
        goalStats={[makeGoalStats({ buffer_usage_rate: 0.25 })]}
        goalCards={[makeGoalCard()]}
        reportRateWindowDays={WINDOW_DAYS}
      />,
    )

    expect(screen.getByText(t('dashboard.stats.bufferUsageRate'))).toBeDefined()
  })

  it('marks the buffer usage rate as unavailable when it could not be computed', () => {
    renderWithProviders(
      <StatsSummary
        goalStats={[makeGoalStats({ buffer_usage_rate: null })]}
        goalCards={[makeGoalCard()]}
        reportRateWindowDays={WINDOW_DAYS}
      />,
    )

    expect(screen.getByText(t('dashboard.stats.bufferUsageRateUnavailable'))).toBeDefined()
  })

  it('drops the buffer usage rate entirely for a reading goal', () => {
    renderWithProviders(
      <StatsSummary
        goalStats={[makeGoalStats({ buffer_usage_rate: null })]}
        goalCards={[makeGoalCard({ category: 'READING' })]}
        reportRateWindowDays={WINDOW_DAYS}
      />,
    )

    expect(screen.queryByText(t('dashboard.stats.bufferUsageRate'))).toBeNull()
    expect(screen.queryByText(t('dashboard.stats.bufferUsageRateUnavailable'))).toBeNull()
  })

  it('shows the window length that came from the settings', () => {
    renderWithProviders(
      <StatsSummary
        goalStats={[makeGoalStats()]}
        goalCards={[makeGoalCard()]}
        reportRateWindowDays={30}
      />,
    )

    expect(
      screen.getByText(t('dashboard.stats.recentReportRate', { windowDays: 30 })),
    ).toBeDefined()
  })

  it('lists the effective speed per material, marking the ones without a value', () => {
    renderWithProviders(
      <StatsSummary
        goalStats={[
          makeGoalStats({
            material_speeds: [
              { material_id: 1, material_name: '教材A', unit_label: '問', speed: 12.345 },
              { material_id: 2, material_name: '教材B', unit_label: '問', speed: null },
            ],
          }),
        ]}
        goalCards={[makeGoalCard()]}
        reportRateWindowDays={WINDOW_DAYS}
      />,
    )

    // 実効速度は小数第2位まで（時間あたりの分量として読み取れる粒度）。
    expect(screen.getByText(/12\.35問/)).toBeDefined()
    // 「算出不可」は予備日消費率でも使う文言のため、教材Bの行に限定して確かめる。
    expect(
      screen.getByText(
        (text) =>
          text.includes('教材B') && text.includes(t('dashboard.stats.effectiveSpeedUnavailable')),
      ),
    ).toBeDefined()
  })

  it('omits the speed list when there is no material', () => {
    renderWithProviders(
      <StatsSummary
        goalStats={[makeGoalStats({ material_speeds: [] })]}
        goalCards={[makeGoalCard()]}
        reportRateWindowDays={WINDOW_DAYS}
      />,
    )

    expect(screen.queryByText(new RegExp(t('dashboard.stats.effectiveSpeed')))).toBeNull()
  })

  it('links each goal to the analytics screen filtered by that goal', () => {
    renderWithProviders(
      <StatsSummary
        goalStats={[makeGoalStats()]}
        goalCards={[makeGoalCard()]}
        reportRateWindowDays={WINDOW_DAYS}
      />,
    )

    expect(
      screen.getByRole('link', { name: t('dashboard.stats.analyticsLink') }).getAttribute('href'),
    ).toContain(`goal=${GOAL_ID}`)
  })
})
