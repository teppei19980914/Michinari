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
  it('marks a fixed exam date', () => {
    const goal = makeGoal({
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
          display_order: 1,
        },
      ],
    })
    expect(resolveAuxiliaryMarkers('2026-08-24', [goal])).toEqual(['EXAM_DATE'])
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
          display_order: 1,
        },
      ],
    })
    expect(resolveAuxiliaryMarkers('2026-08-20', [goal])).toEqual(['EXAM_PERIOD'])
    expect(resolveAuxiliaryMarkers('2026-08-26', [goal])).toEqual(['EXAM_PERIOD'])
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
    expect(resolveAuxiliaryMarkers('2026-08-15', [adjusted])).toEqual(['LOAD_ADJUSTED'])
    expect(resolveAuxiliaryMarkers('2026-08-15', [unadjusted])).toEqual([])
  })

  it('combines markers across multiple active goals without duplicates', () => {
    const goalWithExam = makeGoal({
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
          display_order: 1,
        },
      ],
    })
    const goalWithLoad = makeGoal({
      id: 2,
      load_profiles: [
        { id: 1, goal_id: 2, date_from: '2026-08-24', date_to: '2026-08-24', coefficient: 2, note: null },
      ],
    })
    expect(resolveAuxiliaryMarkers('2026-08-24', [goalWithExam, goalWithLoad]).sort()).toEqual(
      ['EXAM_DATE', 'LOAD_ADJUSTED'].sort(),
    )
  })
})
