import { getDay, parseISO } from 'date-fns'
import { afterEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { setLocale, t } from '../../locales/t'
import { ScheduleGanttHeader } from './ScheduleGanttHeader'

afterEach(() => {
  setLocale('ja')
})

function renderHeader(overrides: Partial<Parameters<typeof ScheduleGanttHeader>[0]> = {}) {
  return render(
    <ScheduleGanttHeader
      rangeStartIso="2026-11-01"
      rangeEndIso="2026-11-10"
      dayWidthRem={2}
      holidayIsoDates={new Set()}
      holidayYearFrom={1955}
      holidayYearTo={2027}
      {...overrides}
    />,
  )
}

describe('ScheduleGanttHeader', () => {
  it('英語表示では月見出しを「略月 年」の形式にする', () => {
    setLocale('en')
    renderHeader()
    expect(screen.getByText('Nov 2026')).not.toBe(null)
  })

  it('同じ月の範囲なら月見出しは1つだけになる', () => {
    renderHeader()
    expect(screen.getByText('2026年11月')).not.toBe(null)
  })

  it('月をまたぐ範囲では月見出しが分かれる', () => {
    renderHeader({ rangeStartIso: '2026-11-25', rangeEndIso: '2026-12-05' })
    expect(screen.getByText('2026年11月')).not.toBe(null)
    expect(screen.getByText('2026年12月')).not.toBe(null)
  })

  it('日の数字を表示期間の日数分表示する', () => {
    renderHeader({ rangeStartIso: '2026-11-01', rangeEndIso: '2026-11-03' })
    expect(screen.getByText('1')).not.toBe(null)
    expect(screen.getByText('2')).not.toBe(null)
    expect(screen.getByText('3')).not.toBe(null)
  })

  it('収録範囲内なら未収録の注記を出さない', () => {
    renderHeader({ rangeStartIso: '2026-11-01', rangeEndIso: '2026-11-03' })
    expect(screen.queryByText(t('schedule.gantt.uncoveredYearNotice', { year: 2026 }))).toBe(null)
  })

  it('収録範囲外の年を含む場合は注記を出す', () => {
    renderHeader({ rangeStartIso: '2028-11-01', rangeEndIso: '2028-11-03' })
    expect(screen.getByText(t('schedule.gantt.uncoveredYearNotice', { year: 2028 }))).not.toBe(
      null,
    )
  })

  it('収録範囲が無い（year_from/year_toがnull）場合は常に未収録として扱う', () => {
    renderHeader({
      rangeStartIso: '2026-11-01',
      rangeEndIso: '2026-11-03',
      holidayYearFrom: null,
      holidayYearTo: null,
    })
    expect(screen.getByText(t('schedule.gantt.uncoveredYearNotice', { year: 2026 }))).not.toBe(
      null,
    )
  })

  it('土曜日の数字セルに土曜用の背景クラスを付ける（D-21）', () => {
    // 2026-11-01〜07の7日間から、date-fnsのgetDayで独立に土曜日を特定する
    // （実装と同じ計算を2重化しない）。
    const rangeStart = '2026-11-01'
    renderHeader({ rangeStartIso: rangeStart, rangeEndIso: '2026-11-07' })
    for (let offset = 0; offset < 7; offset += 1) {
      const date = new Date(2026, 10, 1 + offset)
      const dayNumber = String(date.getDate())
      const cell = screen.getByText(dayNumber)
      if (getDay(date) === 6) {
        expect(cell.className).toContain('bg-schedule-saturday-bg')
      } else if (getDay(date) === 0) {
        expect(cell.className).toContain('bg-schedule-holiday-bg')
      } else {
        expect(cell.className).not.toContain('bg-schedule-saturday-bg')
        expect(cell.className).not.toContain('bg-schedule-holiday-bg')
      }
    }
  })

  it('祝日（平日）の数字セルには日曜・祝日と同じ背景クラスを付ける', () => {
    // 2026-11-03は祝日（文化の日）。平日（火曜）であることをgetDayで確認してから使う。
    const weekday = getDay(parseISO('2026-11-03'))
    expect(weekday).not.toBe(0)
    expect(weekday).not.toBe(6)

    renderHeader({
      rangeStartIso: '2026-11-02',
      rangeEndIso: '2026-11-04',
      holidayIsoDates: new Set(['2026-11-03']),
    })
    expect(screen.getByText('3').className).toContain('bg-schedule-holiday-bg')
  })
})
