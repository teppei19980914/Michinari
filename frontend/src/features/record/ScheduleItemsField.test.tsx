import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { ScheduleItemsField } from './ScheduleItemsField'
import type { GoalScheduleItemsForReportRead } from '../../api/records'
import type { ScheduleItemDraftValue } from './scheduleItemsDraft'

const GOAL: GoalScheduleItemsForReportRead = {
  goal_id: 10,
  goal_name: '資格目標',
  goal_category: 'EXAM',
  items: [
    {
      id: 1,
      title: '第1章',
      planned_start_date: '2026-11-01',
      planned_end_date: '2026-11-10',
      status: 'NOT_STARTED',
      actual_start_date: null,
      actual_end_date: null,
      default_visible: true,
    },
  ],
}

const onChange = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ScheduleItemsField', () => {
  it('renders nothing when there are no eligible goals (D-38)', () => {
    const { container } = render(
      <ScheduleItemsField goals={[]} targetDate="2026-11-05" readOnly={false} values={{}} onChange={onChange} />,
    )
    expect(container.firstChild).toBe(null)
  })

  it('shows the section title and each goal group', () => {
    render(
      <ScheduleItemsField goals={[GOAL]} targetDate="2026-11-05" readOnly={false} values={{}} onChange={onChange} />,
    )
    expect(screen.getByText(t('schedule.dailyReportSection.title'))).toBeTruthy()
    expect(screen.getByText('資格目標')).toBeTruthy()
    expect(screen.getByText('第1章')).toBeTruthy()
  })

  it('renders a group per goal when multiple goals are passed (SC-07)', () => {
    const otherGoal: GoalScheduleItemsForReportRead = {
      goal_id: 20,
      goal_name: '読書目標',
      goal_category: 'READING',
      items: [{ ...GOAL.items[0], id: 2 }],
    }
    render(
      <ScheduleItemsField
        goals={[GOAL, otherGoal]}
        targetDate="2026-11-05"
        readOnly={false}
        values={{}}
        onChange={onChange}
      />,
    )
    expect(screen.getByText('資格目標')).toBeTruthy()
    expect(screen.getByText('読書目標')).toBeTruthy()
  })

  it('merges a row change into the SetStateAction-style onChange', async () => {
    const user = userEvent.setup()
    let latest: Record<number, ScheduleItemDraftValue> = {}
    render(
      <ScheduleItemsField
        goals={[GOAL]}
        targetDate="2026-11-05"
        readOnly={false}
        values={{}}
        onChange={(action) => {
          latest = typeof action === 'function' ? action(latest) : action
        }}
      />,
    )
    await user.selectOptions(
      screen.getByRole('combobox', { name: t('schedule.columns.status') }),
      t('schedule.status.IN_PROGRESS'),
    )
    expect(latest[1]).toEqual({
      status: 'IN_PROGRESS',
      actualStartDate: '2026-11-05',
      actualEndDate: null,
      touched: true,
    })
  })
})
