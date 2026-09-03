import { describe, expect, it } from 'vitest'
import { groupByGoal } from './groupByGoal'

type Item = { goal_id: number; goal_name: string; label: string }

describe('groupByGoal', () => {
  it('returns an empty array for an empty input', () => {
    expect(groupByGoal<Item>([])).toEqual([])
  })

  it('groups items under a single goal when only one goal is present', () => {
    const items: Item[] = [
      { goal_id: 1, goal_name: '目標A', label: '教材A' },
      { goal_id: 1, goal_name: '目標A', label: '教材B' },
    ]

    expect(groupByGoal(items)).toEqual([
      { goalId: 1, goalName: '目標A', items },
    ])
  })

  it('groups items by goal_id, preserving the order goals first appear in', () => {
    const itemA1: Item = { goal_id: 1, goal_name: '目標A', label: '教材A-1' }
    const itemB1: Item = { goal_id: 2, goal_name: '目標B', label: '教材B-1' }
    const itemA2: Item = { goal_id: 1, goal_name: '目標A', label: '教材A-2' }

    const groups = groupByGoal([itemA1, itemB1, itemA2])

    expect(groups).toEqual([
      { goalId: 1, goalName: '目標A', items: [itemA1, itemA2] },
      { goalId: 2, goalName: '目標B', items: [itemB1] },
    ])
  })
})
