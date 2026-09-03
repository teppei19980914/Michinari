import { describe, expect, it } from 'vitest'
import { resolveAuxiliaryMarkers } from './resolveAuxiliaryMarkers'
import type { components } from '../../types/api.d.ts'

type GoalDetailRead = components['schemas']['GoalDetailRead']

function makeGoal(overrides: Partial<GoalDetailRead>): GoalDetailRead {
  return {
    id: 1,
    name: '目標A',
    start_date: '2026-01-01',
    status: 'ACTIVE',
    resource_ratio: 1,
    memo: null,
    activated_at: null,
    closed_at: null,
    exam_subjects: [],
    materials: [],
    load_profiles: [],
    ...overrides,
  } as GoalDetailRead
}

describe('resolveAuxiliaryMarkers', () => {
  it('marks a fixed exam date, attributed to the goal', () => {
    const goal = makeGoal({
      id: 1,
      name: '目標A',
      exam_subjects: [
        {
          id: 1,
          goal_id: 1,
          name: '科目A',
          exam_date_type: 'FIXED',
          exam_date_from: null,
          exam_date_to: null,
          exam_date_fixed: '2026-08-24',
          passing_score: null,
          passing_score_type: 'PERCENTAGE',
          passing_score_max: null,
          display_order: 1,
        },
      ],
    })
    expect(resolveAuxiliaryMarkers('2026-08-24', [goal])).toEqual([
      { marker: 'EXAM_DATE', goal_id: 1, goal_name: '目標A' },
    ])
  })

  it('marks an exam period (range type) inclusively', () => {
    const goal = makeGoal({
      exam_subjects: [
        {
          id: 1,
          goal_id: 1,
          name: '科目A',
          exam_date_type: 'RANGE',
          exam_date_from: '2026-08-20',
          exam_date_to: '2026-08-26',
          exam_date_fixed: null,
          passing_score: null,
          passing_score_type: 'PERCENTAGE',
          passing_score_max: null,
          display_order: 1,
        },
      ],
    })
    expect(resolveAuxiliaryMarkers('2026-08-20', [goal])).toEqual([
      { marker: 'EXAM_PERIOD', goal_id: 1, goal_name: '目標A' },
    ])
    expect(resolveAuxiliaryMarkers('2026-08-26', [goal])).toEqual([
      { marker: 'EXAM_PERIOD', goal_id: 1, goal_name: '目標A' },
    ])
    expect(resolveAuxiliaryMarkers('2026-08-27', [goal])).toEqual([])
  })

  it('marks a load-adjusted period only when the coefficient differs from 1.0', () => {
    const adjusted = makeGoal({
      load_profiles: [
        { id: 1, goal_id: 1, date_from: '2026-08-01', date_to: '2026-08-31', coefficient: 0.5, note: null },
      ],
    })
    const unadjusted = makeGoal({
      load_profiles: [
        { id: 1, goal_id: 1, date_from: '2026-08-01', date_to: '2026-08-31', coefficient: 1, note: null },
      ],
    })
    expect(resolveAuxiliaryMarkers('2026-08-15', [adjusted])).toEqual([
      { marker: 'LOAD_ADJUSTED', goal_id: 1, goal_name: '目標A' },
    ])
    expect(resolveAuxiliaryMarkers('2026-08-15', [unadjusted])).toEqual([])
  })

  it('deduplicates repeated markers of the same kind within a single goal', () => {
    const goal = makeGoal({
      id: 1,
      exam_subjects: [
        {
          id: 1,
          goal_id: 1,
          name: '科目A',
          exam_date_type: 'FIXED',
          exam_date_from: null,
          exam_date_to: null,
          exam_date_fixed: '2026-08-24',
          passing_score: null,
          passing_score_type: 'PERCENTAGE',
          passing_score_max: null,
          display_order: 1,
        },
        {
          id: 2,
          goal_id: 1,
          name: '科目B',
          exam_date_type: 'FIXED',
          exam_date_from: null,
          exam_date_to: null,
          exam_date_fixed: '2026-08-24',
          passing_score: null,
          passing_score_type: 'PERCENTAGE',
          passing_score_max: null,
          display_order: 2,
        },
      ],
    })
    expect(resolveAuxiliaryMarkers('2026-08-24', [goal])).toEqual([
      { marker: 'EXAM_DATE', goal_id: 1, goal_name: '目標A' },
    ])
  })

  it('attributes markers from multiple active goals to their own goal, without cross-goal deduplication', () => {
    const goalWithExam = makeGoal({
      id: 1,
      name: '目標A',
      exam_subjects: [
        {
          id: 1,
          goal_id: 1,
          name: '科目A',
          exam_date_type: 'FIXED',
          exam_date_from: null,
          exam_date_to: null,
          exam_date_fixed: '2026-08-24',
          passing_score: null,
          passing_score_type: 'PERCENTAGE',
          passing_score_max: null,
          display_order: 1,
        },
      ],
    })
    const goalWithLoad = makeGoal({
      id: 2,
      name: '目標B',
      load_profiles: [
        { id: 1, goal_id: 2, date_from: '2026-08-24', date_to: '2026-08-24', coefficient: 2, note: null },
      ],
    })
    expect(resolveAuxiliaryMarkers('2026-08-24', [goalWithExam, goalWithLoad])).toEqual([
      { marker: 'EXAM_DATE', goal_id: 1, goal_name: '目標A' },
      { marker: 'LOAD_ADJUSTED', goal_id: 2, goal_name: '目標B' },
    ])
  })

  it('keeps both goals visible when they share the same marker kind on the same date', () => {
    const goalA = makeGoal({
      id: 1,
      name: '目標A',
      exam_subjects: [
        {
          id: 1,
          goal_id: 1,
          name: '科目A',
          exam_date_type: 'FIXED',
          exam_date_from: null,
          exam_date_to: null,
          exam_date_fixed: '2026-08-24',
          passing_score: null,
          passing_score_type: 'PERCENTAGE',
          passing_score_max: null,
          display_order: 1,
        },
      ],
    })
    const goalB = makeGoal({
      id: 2,
      name: '目標B',
      exam_subjects: [
        {
          id: 2,
          goal_id: 2,
          name: '科目B',
          exam_date_type: 'FIXED',
          exam_date_from: null,
          exam_date_to: null,
          exam_date_fixed: '2026-08-24',
          passing_score: null,
          passing_score_type: 'PERCENTAGE',
          passing_score_max: null,
          display_order: 1,
        },
      ],
    })

    const result = resolveAuxiliaryMarkers('2026-08-24', [goalA, goalB])

    // 目標をまたいだ重複排除は行わないため、同じ種別でも両方の目標分が残ること
    // （旧Set実装ではここで片方が消えていた回帰）。
    expect(result).toHaveLength(2)
    expect(result.map((item) => item.goal_id).sort()).toEqual([1, 2])
  })
})
