import { describe, expect, it } from 'vitest'
import { resolveMilestoneIcon, resolveMilestoneMessage } from './milestoneContent'
import type { MilestoneAchievement, MilestoneType } from '../../api/milestones'

function makeAchievement(
  milestoneType: MilestoneType,
  milestoneKey: string,
): MilestoneAchievement {
  return {
    id: 1,
    goal_id: 1,
    milestone_type: milestoneType,
    milestone_key: milestoneKey,
    achieved_at: '2026-01-01T00:00:00',
    celebrated_at: null,
  }
}

describe('resolveMilestoneIcon', () => {
  it('resolves exam/reading/work icons by category', () => {
    expect(resolveMilestoneIcon('EXAM')).toBe('exam')
    expect(resolveMilestoneIcon('READING')).toBe('reading')
    expect(resolveMilestoneIcon('WORK')).toBe('work')
  })
})

describe('resolveMilestoneMessage', () => {
  it('includes the threshold for consecutive days', () => {
    expect(resolveMilestoneMessage(makeAchievement('CONSECUTIVE_DAYS', '7'))).toContain('7')
  })

  it('includes the threshold for total record days', () => {
    expect(resolveMilestoneMessage(makeAchievement('TOTAL_RECORD_DAYS', '30'))).toContain('30')
  })

  it('includes the threshold for reading total pages', () => {
    expect(resolveMilestoneMessage(makeAchievement('READING_TOTAL_PAGES', '500'))).toContain('500')
  })

  it('includes the threshold for reading completed books', () => {
    expect(resolveMilestoneMessage(makeAchievement('READING_COMPLETED_BOOKS', '3'))).toContain('3')
  })

  it('extracts the cycle number from the material:cycle key', () => {
    expect(
      resolveMilestoneMessage(makeAchievement('EXAM_MATERIAL_CYCLE_COMPLETED', '42:2')),
    ).toContain('2')
  })

  it('includes the threshold for exam overall progress', () => {
    expect(resolveMilestoneMessage(makeAchievement('EXAM_OVERALL_PROGRESS', '50'))).toContain('50')
  })

  it('includes the threshold for work record count', () => {
    expect(resolveMilestoneMessage(makeAchievement('WORK_RECORD_COUNT', '10'))).toContain('10')
  })

  it('returns a fixed message for work evaluation period completion', () => {
    expect(
      resolveMilestoneMessage(makeAchievement('WORK_EVALUATION_PERIOD_COMPLETED', '2026-H1')),
    ).not.toBe('')
  })
})
