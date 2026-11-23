import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ScheduleGanttRow } from './ScheduleGanttRow'
import type { ScheduleGanttItemInput } from './scheduleGanttGeometry'

const RANGE_START = '2026-11-01'
const DAY_WIDTH = 2
const TODAY = '2026-11-23'

function baseItem(overrides: Partial<ScheduleGanttItemInput>): ScheduleGanttItemInput {
  return {
    status: 'NOT_STARTED',
    planned_start_date: '2026-11-05',
    planned_end_date: '2026-11-10',
    actual_start_date: null,
    actual_end_date: null,
    ...overrides,
  }
}

describe('ScheduleGanttRow', () => {
  it('未着手は予定帯のみで実績帯を持たない', () => {
    render(
      <ScheduleGanttRow
        title="作業A"
        item={baseItem({})}
        rangeStartIso={RANGE_START}
        dayWidthRem={DAY_WIDTH}
        today={TODAY}
      />,
    )
    expect(screen.getByTestId('planned-band')).not.toBe(null)
    expect(screen.queryByTestId('actual-band')).toBe(null)
  })

  it('進行中で遅れている場合はアクセント色の実績帯と遅れの印を表示する', () => {
    render(
      <ScheduleGanttRow
        title="作業A"
        item={baseItem({
          status: 'IN_PROGRESS',
          planned_end_date: '2026-11-10',
          actual_start_date: '2026-11-05',
        })}
        rangeStartIso={RANGE_START}
        dayWidthRem={DAY_WIDTH}
        today={TODAY}
      />,
    )
    const actualBand = screen.getByTestId('actual-band')
    expect(actualBand.className).toContain('bg-accent')
    expect(screen.getByTestId('delay-mark')).not.toBe(null)
  })

  it('期限内に完了した場合は成功色の実績帯で遅れの印は出さない', () => {
    render(
      <ScheduleGanttRow
        title="作業A"
        item={baseItem({
          status: 'DONE',
          planned_end_date: '2026-11-15',
          actual_start_date: '2026-11-05',
          actual_end_date: '2026-11-10',
        })}
        rangeStartIso={RANGE_START}
        dayWidthRem={DAY_WIDTH}
        today={TODAY}
      />,
    )
    const actualBand = screen.getByTestId('actual-band')
    expect(actualBand.className).toContain('bg-success')
    expect(screen.queryByTestId('delay-mark')).toBe(null)
  })

  it('中止はグレーの実績帯を表示する', () => {
    render(
      <ScheduleGanttRow
        title="作業A"
        item={baseItem({ status: 'CANCELLED', actual_start_date: '2026-11-05' })}
        rangeStartIso={RANGE_START}
        dayWidthRem={DAY_WIDTH}
        today={TODAY}
      />,
    )
    expect(screen.getByTestId('actual-band').className).toContain('bg-border-strong')
  })

  it('Tooltipに作業項目名・予定期間・実績の有無を表示する', () => {
    render(
      <ScheduleGanttRow
        title="作業A"
        item={baseItem({})}
        rangeStartIso={RANGE_START}
        dayWidthRem={DAY_WIDTH}
        today={TODAY}
      />,
    )
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip.textContent).toContain('作業A')
    expect(tooltip.textContent).toContain('11/5')
    expect(tooltip.textContent).toContain('11/10')
  })
})
