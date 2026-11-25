import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleItemsGoalGroup } from './ScheduleItemsGoalGroup'
import type { GoalScheduleItemsForReportRead } from '../../api/records'

const VISIBLE_ITEM = {
  id: 1,
  title: '第1章',
  planned_start_date: '2026-11-01',
  planned_end_date: '2026-11-10',
  status: 'NOT_STARTED' as const,
  actual_start_date: null,
  actual_end_date: null,
  default_visible: true,
}

const HIDDEN_ITEM = {
  id: 2,
  title: '第2章（先）',
  planned_start_date: '2026-12-01',
  planned_end_date: '2026-12-10',
  status: 'NOT_STARTED' as const,
  actual_start_date: null,
  actual_end_date: null,
  default_visible: false,
}

const GOAL: GoalScheduleItemsForReportRead = {
  goal_id: 10,
  goal_name: '資格目標',
  goal_category: 'EXAM',
  items: [VISIBLE_ITEM, HIDDEN_ITEM],
}

const onChange = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleItemsGoalGroup', () => {
  it('shows the goal name and only the default-visible rows at first', () => {
    render(
      <ScheduleItemsGoalGroup
        goal={GOAL}
        targetDate="2026-11-05"
        readOnly={false}
        values={{}}
        onChange={onChange}
      />,
    )
    expect(screen.getByText('資格目標')).toBeTruthy()
    expect(screen.getByText('第1章')).toBeTruthy()
    expect(screen.queryByText('第2章（先）')).toBe(null)
  })

  it('expands to every row when "show all" is pressed, and can collapse again', async () => {
    const user = userEvent.setup()
    render(
      <ScheduleItemsGoalGroup
        goal={GOAL}
        targetDate="2026-11-05"
        readOnly={false}
        values={{}}
        onChange={onChange}
      />,
    )

    await user.click(screen.getByRole('button', { name: t('schedule.dailyReportSection.showAll') }))
    expect(screen.getByText('第2章（先）')).toBeTruthy()

    await user.click(screen.getByRole('button', { name: t('schedule.dailyReportSection.collapse') }))
    expect(screen.queryByText('第2章（先）')).toBe(null)
  })

  it('shows the empty-rows message when every row is hidden by default', () => {
    const allHidden: GoalScheduleItemsForReportRead = { ...GOAL, items: [HIDDEN_ITEM] }
    render(
      <ScheduleItemsGoalGroup
        goal={allHidden}
        targetDate="2026-11-05"
        readOnly={false}
        values={{}}
        onChange={onChange}
      />,
    )
    expect(screen.getByText(t('schedule.dailyReportSection.noRows'))).toBeTruthy()
  })

  it('hides the "show all" button when every row is already default-visible', () => {
    const allVisible: GoalScheduleItemsForReportRead = { ...GOAL, items: [VISIBLE_ITEM] }
    render(
      <ScheduleItemsGoalGroup
        goal={allVisible}
        targetDate="2026-11-05"
        readOnly={false}
        values={{}}
        onChange={onChange}
      />,
    )
    expect(screen.queryByRole('button')).toBe(null)
  })

  it('uses the draft value when present, falling back to the fetched item otherwise', async () => {
    const user = userEvent.setup()
    render(
      <ScheduleItemsGoalGroup
        goal={{ ...GOAL, items: [VISIBLE_ITEM] }}
        targetDate="2026-11-05"
        readOnly={false}
        values={{
          1: { status: 'IN_PROGRESS', actualStartDate: '2026-11-05', actualEndDate: null, touched: true },
        }}
        onChange={onChange}
      />,
    )
    expect(
      (screen.getByRole('combobox', { name: t('schedule.columns.status') }) as HTMLSelectElement)
        .value,
    ).toBe('IN_PROGRESS')

    await user.selectOptions(
      screen.getByRole('combobox', { name: t('schedule.columns.status') }),
      t('schedule.status.DONE'),
    )
    expect(onChange).toHaveBeenCalledWith(1, {
      status: 'DONE',
      actualStartDate: '2026-11-05',
      actualEndDate: '2026-11-05',
      touched: true,
    })
  })
})
