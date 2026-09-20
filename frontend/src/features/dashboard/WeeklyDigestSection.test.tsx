/** 先週のまとめ（仕様書6.1、S-4 4-4）の表示条件を固定する。
 *
 * 表示内容の判定自体（AI要約優先・非AI集計へのフォールバック）は
 * resolveWeeklyDigestDisplay.test.tsで検証済みのため、ここでは各判定結果が
 * 正しく画面へ反映されることのみを確認する。 */
import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { makeWeeklyDigest } from '../../test/fixtures'
import { WeeklyDigestSection } from './WeeklyDigestSection'

describe('WeeklyDigestSection', () => {
  it('renders nothing when there is no digest for the selected goal', () => {
    const { container } = renderWithProviders(<WeeklyDigestSection digest={null} />)

    expect(container.textContent).toBe('')
  })

  it('shows the week range and the AI summary text when available', () => {
    renderWithProviders(
      <WeeklyDigestSection
        digest={makeWeeklyDigest({
          week_start_date: '2026-09-01',
          week_end_date: '2026-09-07',
          ai_summary_text: '先週はよく頑張りました。',
        })}
      />,
    )

    expect(screen.getByText(t('dashboard.weeklyDigest.title'))).toBeDefined()
    expect(screen.getByText('9/1〜9/7')).toBeDefined()
    expect(screen.getByText('先週はよく頑張りました。')).toBeDefined()
  })

  it('shows a "no records" notice when there is no AI summary and no records', () => {
    renderWithProviders(
      <WeeklyDigestSection
        digest={makeWeeklyDigest({ ai_summary_text: null, recorded_days: 0, total_minutes: null })}
      />,
    )

    expect(screen.getByText(t('dashboard.weeklyDigest.noRecords'))).toBeDefined()
  })

  it('shows the non-AI record summary (days and minutes) when there is no AI summary', () => {
    renderWithProviders(
      <WeeklyDigestSection
        digest={makeWeeklyDigest({ ai_summary_text: null, recorded_days: 3, total_minutes: 120 })}
      />,
    )

    expect(
      screen.getByText(t('dashboard.weeklyDigest.recordedDays', { days: 3 }), { exact: false }),
    ).toBeDefined()
    expect(
      screen.getByText(t('dashboard.weeklyDigest.totalMinutes', { minutes: 120 }), {
        exact: false,
      }),
    ).toBeDefined()
  })

  it('omits the total minutes when the category does not track time (reading/work)', () => {
    renderWithProviders(
      <WeeklyDigestSection
        digest={makeWeeklyDigest({ ai_summary_text: null, recorded_days: 2, total_minutes: null })}
      />,
    )

    expect(
      screen.getByText(t('dashboard.weeklyDigest.recordedDays', { days: 2 }), { exact: false }),
    ).toBeDefined()
    expect(screen.queryByText(/投下時間/)).toBeNull()
  })
})
