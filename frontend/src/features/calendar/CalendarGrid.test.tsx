/** カレンダー本体（月グリッド）の補助表示を固定する（Phase 36）。
 *
 * 補助マーカーは目標IDを伴って渡される（resolveAuxiliaryMarkers.ts）。1目標分だけなら
 * 目標名を出さず、複数目標分が同じ日に重なったときだけ「目標名: 種別」の形にする。
 * カレンダー画面（SC-05）は現在1目標分しか渡さない（Phase25で選択中の1目標のみに改めた）
 * ため、この出し分けは部品としての契約であり、画面側からは通せない。ここで直接固定する。
 *
 * 日種別ごとの背景色・記録状態のマーカーは calendarCellStyle.test.ts が担うため扱わない。 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { CalendarDayRead } from '../../api/calendar'
import type { AttributedAuxiliaryMarker } from './resolveAuxiliaryMarkers'
import { CalendarGrid } from './CalendarGrid'

const MONTH = new Date(Date.UTC(2026, 8, 1))
const TARGET_DATE = '2026-09-13'

const FIRST_GOAL = { id: 1, name: '目標A' }
const SECOND_GOAL = { id: 2, name: '目標B' }

const EXAM_DATE_LABEL = t('calendar.auxiliaryMarker.EXAM_DATE')
const LOAD_ADJUSTED_LABEL = t('calendar.auxiliaryMarker.LOAD_ADJUSTED')

function marker(
  goal: { id: number; name: string },
  kind: AttributedAuxiliaryMarker['marker'],
): AttributedAuxiliaryMarker {
  return { marker: kind, goal_id: goal.id, goal_name: goal.name }
}

function renderGrid(markers: AttributedAuxiliaryMarker[]) {
  const day: CalendarDayRead = {
    target_date: TARGET_DATE,
    day_type: 'PLAN',
    record_state: null,
  }
  return renderWithProviders(
    <CalendarGrid
      month={MONTH}
      daysByDate={new Map([[TARGET_DATE, day]])}
      auxiliaryMarkersByDate={new Map([[TARGET_DATE, markers]])}
      onSelectDate={vi.fn()}
      onEditDayType={vi.fn()}
    />,
  )
}

afterEach(() => {
  cleanup()
})

describe('CalendarGrid の補助表示', () => {
  it('shows no marker text for a day that has none', () => {
    renderGrid([])
    expect(screen.queryByText(new RegExp(EXAM_DATE_LABEL))).toBe(null)
  })

  it('omits the goal name while every marker of the day belongs to one goal', () => {
    renderGrid([marker(FIRST_GOAL, 'EXAM_DATE'), marker(FIRST_GOAL, 'LOAD_ADJUSTED')])
    const cell = screen.getByText(new RegExp(EXAM_DATE_LABEL))
    expect(cell.textContent).toBe(`${EXAM_DATE_LABEL} / ${LOAD_ADJUSTED_LABEL}`)
    expect(cell.textContent).not.toContain(FIRST_GOAL.name)
  })

  it('heads each line with the goal name once two goals share the day', () => {
    // どちらの目標の受験日か分からないと、同じ日に2件並ぶ意味が読み取れない。
    renderGrid([marker(FIRST_GOAL, 'EXAM_DATE'), marker(SECOND_GOAL, 'EXAM_DATE')])
    expect(
      screen.getByText(`${FIRST_GOAL.name}: ${EXAM_DATE_LABEL}`),
    ).toBeTruthy()
    expect(
      screen.getByText(`${SECOND_GOAL.name}: ${EXAM_DATE_LABEL}`),
    ).toBeTruthy()
  })
})
