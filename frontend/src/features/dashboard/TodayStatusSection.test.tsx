/** 「本日の報告ボタンがどこへ遷移するか」の回帰テスト。1カテゴリだけ確定した日に残りの
 * カテゴリを報告できるかを左右する（仕様書1.1（改20））。遷移先は分岐を持たない定数のため
 * 純粋関数側では守れず、描画結果のリンク先として固定する（vite.config.tsのcoverage include
 * が言う「押した結果まで含めて守りたいもの」に該当）。 */
import { describe, expect, it, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { t } from '../../locales/t'
import { TodayStatusSection } from './TodayStatusSection'

const LOGICAL_DATE = '2026-09-12'

function renderSection(recordState: 'REPORTED' | 'PROGRESS_ONLY' | null) {
  render(
    <MemoryRouter>
      <TodayStatusSection logicalDate={LOGICAL_DATE} recordState={recordState} />
    </MemoryRouter>,
  )
  return screen.getByRole('link')
}

afterEach(() => {
  cleanup()
})

describe('TodayStatusSection', () => {
  it('links to the daily report screen when nothing is reported yet', () => {
    expect(renderSection(null).getAttribute('href')).toBe(`/records/${LOGICAL_DATE}/report`)
  })

  it('links to the daily report screen when only some categories are finalized (regression: the aggregated state is REPORTED, but the remaining categories must stay reportable)', () => {
    expect(renderSection('REPORTED').getAttribute('href')).toBe(
      `/records/${LOGICAL_DATE}/report`,
    )
  })

  it('keeps showing the aggregated state as the label', () => {
    renderSection('REPORTED')
    expect(
      screen.getByText(
        `${t('dashboard.todayStatus.label')}：${t('dashboard.todayStatus.reported')}`,
      ),
    ).toBeTruthy()
  })

  it('falls back to the unreported label when no category has been touched', () => {
    renderSection(null)
    expect(
      screen.getByText(
        `${t('dashboard.todayStatus.label')}：${t('dashboard.todayStatus.unreported')}`,
      ),
    ).toBeTruthy()
  })

  it('shows the progress-only label', () => {
    renderSection('PROGRESS_ONLY')
    expect(
      screen.getByText(
        `${t('dashboard.todayStatus.label')}：${t('dashboard.todayStatus.progressOnly')}`,
      ),
    ).toBeTruthy()
  })
})
