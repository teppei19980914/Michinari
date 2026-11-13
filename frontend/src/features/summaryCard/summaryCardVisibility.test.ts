import { describe, expect, it } from 'vitest'
import { createDefaultVisibility, toggleVisibility } from './summaryCardVisibility'

describe('createDefaultVisibility', () => {
  it('全項目を表示にする', () => {
    expect(createDefaultVisibility()).toEqual({
      recordDays: true,
      longestConsecutiveDays: true,
      topTheme: true,
      milestones: true,
      roadmap: true,
      aiSentence: true,
    })
  })
})

describe('toggleVisibility', () => {
  it('指定した項目だけを更新する', () => {
    const current = createDefaultVisibility()
    const next = toggleVisibility(current, 'milestones', false)
    expect(next.milestones).toBe(false)
    expect(next.recordDays).toBe(true)
    expect(current.milestones).toBe(true)
  })
})
