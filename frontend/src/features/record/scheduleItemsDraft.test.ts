import { describe, expect, it } from 'vitest'
import {
  buildScheduleItemUpdatesPayload,
  collectAllScheduleItemIds,
  initScheduleItemDraftValues,
  selectScheduleItemIdsForGoals,
} from './scheduleItemsDraft'
import type { GoalScheduleItemsForReportRead } from '../../api/records'

const EXAM_GOAL_ITEMS: GoalScheduleItemsForReportRead = {
  goal_id: 1,
  goal_name: '資格目標',
  goal_category: 'EXAM',
  items: [
    {
      id: 10,
      title: '第1章',
      planned_start_date: '2026-01-01',
      planned_end_date: '2026-01-10',
      status: 'NOT_STARTED',
      actual_start_date: null,
      actual_end_date: null,
      default_visible: true,
    },
  ],
}

const READING_GOAL_ITEMS: GoalScheduleItemsForReportRead = {
  goal_id: 2,
  goal_name: '読書目標',
  goal_category: 'READING',
  items: [
    {
      id: 20,
      title: '第1部',
      planned_start_date: '2026-01-01',
      planned_end_date: '2026-01-10',
      status: 'IN_PROGRESS',
      actual_start_date: '2026-01-02',
      actual_end_date: null,
      default_visible: true,
    },
  ],
}

describe('initScheduleItemDraftValues', () => {
  it('builds untouched draft values keyed by schedule item id', () => {
    const values = initScheduleItemDraftValues([EXAM_GOAL_ITEMS, READING_GOAL_ITEMS])

    expect(values).toEqual({
      10: { status: 'NOT_STARTED', actualStartDate: null, actualEndDate: null, touched: false },
      20: {
        status: 'IN_PROGRESS',
        actualStartDate: '2026-01-02',
        actualEndDate: null,
        touched: false,
      },
    })
  })

  it('returns an empty object when there are no goals', () => {
    expect(initScheduleItemDraftValues([])).toEqual({})
  })
})

describe('selectScheduleItemIdsForGoals', () => {
  it('collects item ids only from the specified goals', () => {
    const ids = selectScheduleItemIdsForGoals([EXAM_GOAL_ITEMS, READING_GOAL_ITEMS], new Set([1]))
    expect(ids).toEqual(new Set([10]))
  })

  it('returns an empty set when no goal matches', () => {
    const ids = selectScheduleItemIdsForGoals([EXAM_GOAL_ITEMS], new Set([999]))
    expect(ids).toEqual(new Set())
  })
})

describe('collectAllScheduleItemIds', () => {
  it('collects item ids across all goals regardless of category', () => {
    const ids = collectAllScheduleItemIds([EXAM_GOAL_ITEMS, READING_GOAL_ITEMS])
    expect(ids).toEqual(new Set([10, 20]))
  })

  it('returns an empty set when there are no goals', () => {
    expect(collectAllScheduleItemIds([])).toEqual(new Set())
  })
})

describe('buildScheduleItemUpdatesPayload', () => {
  it('excludes rows that were not touched', () => {
    const values = initScheduleItemDraftValues([EXAM_GOAL_ITEMS])
    const payload = buildScheduleItemUpdatesPayload(values, new Set([10]))
    expect(payload).toEqual([])
  })

  it('includes only touched rows that belong to the eligible id set', () => {
    const values = {
      10: { status: 'IN_PROGRESS' as const, actualStartDate: '2026-01-03', actualEndDate: null, touched: true },
      20: { status: 'DONE' as const, actualStartDate: '2026-01-02', actualEndDate: '2026-01-05', touched: true },
    }

    const payload = buildScheduleItemUpdatesPayload(values, new Set([10]))

    expect(payload).toEqual([
      {
        schedule_item_id: 10,
        status: 'IN_PROGRESS',
        actual_start_date: '2026-01-03',
        actual_end_date: null,
      },
    ])
  })
})
