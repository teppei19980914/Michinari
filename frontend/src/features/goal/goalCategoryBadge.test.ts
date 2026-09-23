import { describe, expect, it } from 'vitest'
import { GOAL_CATEGORIES } from '../../constants/goalCategories'
import { CHARACTER_ICONS } from '../../constants/characterIcons'
import { resolveGoalCategoryBadgeClass, resolveGoalCategoryIcon } from './goalCategoryBadge'

describe('resolveGoalCategoryBadgeClass', () => {
  it('assigns a distinct color to each goal category', () => {
    const classes = GOAL_CATEGORIES.map(resolveGoalCategoryBadgeClass)

    expect(new Set(classes).size).toBe(classes.length)
  })

  it.each([
    ['EXAM', 'bg-blue-100 text-blue-800'],
    ['READING', 'bg-emerald-100 text-emerald-800'],
    ['WORK', 'bg-amber-100 text-amber-800'],
  ] as const)('maps %s to %s', (category, expected) => {
    expect(resolveGoalCategoryBadgeClass(category)).toBe(expected)
  })
})

describe('resolveGoalCategoryIcon', () => {
  it('assigns a distinct icon to each goal category', () => {
    const icons = GOAL_CATEGORIES.map(resolveGoalCategoryIcon)

    expect(new Set(icons).size).toBe(icons.length)
  })

  it.each([
    ['EXAM', CHARACTER_ICONS.exam],
    ['READING', CHARACTER_ICONS.reading],
    ['WORK', CHARACTER_ICONS.work],
  ] as const)('maps %s to its UI-08/09/10 icon', (category, expected) => {
    expect(resolveGoalCategoryIcon(category)).toBe(expected)
  })
})
