import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ScheduleGanttOverlay } from './ScheduleGanttOverlay'

describe('ScheduleGanttOverlay', () => {
  it('土曜・祝日の矩形と本日線を、渡された位置・幅で描く', () => {
    render(
      <ScheduleGanttOverlay
        dayTypeRuns={[
          { type: 'saturday', leftRem: 10, widthRem: 2 },
          { type: 'holiday', leftRem: 12, widthRem: 2 },
        ]}
        todayLineLeftRem={20}
      />,
    )
    const saturday = screen.getByTestId('day-type-run-saturday')
    expect(saturday.style.left).toBe('10rem')
    expect(saturday.style.width).toBe('2rem')

    const holiday = screen.getByTestId('day-type-run-holiday')
    expect(holiday.style.left).toBe('12rem')

    const todayLine = screen.getByTestId('today-line')
    expect(todayLine.style.left).toBe('20rem')
  })

  it('区間が無い場合は本日線だけを描く', () => {
    render(<ScheduleGanttOverlay dayTypeRuns={[]} todayLineLeftRem={5} />)
    expect(screen.queryByTestId('day-type-run-saturday')).toBe(null)
    expect(screen.queryByTestId('day-type-run-holiday')).toBe(null)
    expect(screen.getByTestId('today-line')).not.toBe(null)
  })
})
