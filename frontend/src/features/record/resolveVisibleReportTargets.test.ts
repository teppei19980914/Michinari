import { describe, expect, it } from 'vitest'
import type { BookRead, GoalRead, WorkAssignmentRead } from '../../api/goals'
import type { GoalScheduleItemsForReportRead, QuotaItemRead } from '../../api/records'
import {
  resolveVisibleReportTargets,
  type VisibleReportTargetsInput,
} from './resolveVisibleReportTargets'

function buildScheduleItemGoal(
  goal: GoalRead,
  overrides: Partial<GoalScheduleItemsForReportRead> = {},
): GoalScheduleItemsForReportRead {
  return {
    goal_id: goal.id,
    goal_name: goal.name,
    goal_category: goal.category,
    items: [
      {
        id: goal.id * 100,
        title: '作業A',
        planned_start_date: '2026-01-01',
        planned_end_date: '2026-01-10',
        status: 'NOT_STARTED',
        actual_start_date: null,
        actual_end_date: null,
        default_visible: true,
      },
    ],
    ...overrides,
  }
}

function buildGoal(id: number, category: GoalRead['category']): GoalRead {
  return { id, category, name: `goal-${id}`, status: 'ACTIVE' } as GoalRead
}

const EXAM_GOAL = buildGoal(1, 'EXAM')
const OTHER_EXAM_GOAL = buildGoal(2, 'EXAM')
const READING_GOAL = buildGoal(3, 'READING')
const WORK_GOAL = buildGoal(4, 'WORK')

const EXAM_QUOTA = { material_id: 10, goal_id: EXAM_GOAL.id } as QuotaItemRead
const OTHER_EXAM_QUOTA = { material_id: 11, goal_id: OTHER_EXAM_GOAL.id } as QuotaItemRead
const BOOK = { id: 20, title: 'book' } as BookRead
const WORK_ASSIGNMENT = { id: 30, client_name: 'client' } as WorkAssignmentRead

function buildInput(overrides: Partial<VisibleReportTargetsInput> = {}): VisibleReportTargetsInput {
  return {
    showGoalSelector: false,
    selectedGoal: undefined,
    goals: [EXAM_GOAL],
    quotaItems: [EXAM_QUOTA],
    readingBooks: [{ goal: READING_GOAL, book: BOOK }],
    workAssignments: [{ goal: WORK_GOAL, workAssignment: WORK_ASSIGNMENT }],
    scheduleItems: [],
    ...overrides,
  }
}

describe('resolveVisibleReportTargets', () => {
  describe('without the goal tab bar (0〜1件の着手中目標)', () => {
    it('shows every category that has a target, without filtering', () => {
      const result = resolveVisibleReportTargets(buildInput())

      expect(result.quotaItems).toEqual([EXAM_QUOTA])
      expect(result.diaryGoals).toEqual([EXAM_GOAL])
      expect(result.books).toEqual([BOOK])
      expect(result.workAssignments).toEqual([WORK_ASSIGNMENT])
      expect(result.showExamSection).toBe(true)
      expect(result.showReadingSection).toBe(true)
      expect(result.showWorkSection).toBe(true)
    })

    it('hides a category that has no target at all', () => {
      // 資格試験目標を持たない利用者に空のセクションと確定ボタンを出さない（2026-09-05）。
      const result = resolveVisibleReportTargets(
        buildInput({ goals: [], readingBooks: [], workAssignments: [] }),
      )

      expect(result.showExamSection).toBe(false)
      expect(result.showReadingSection).toBe(false)
      expect(result.showWorkSection).toBe(false)
    })

    it('keeps the exam section visible even when the goal has no material with a quota', () => {
      const result = resolveVisibleReportTargets(buildInput({ quotaItems: [] }))

      expect(result.showExamSection).toBe(true)
      expect(result.quotaItems).toEqual([])
    })

    it('splits scheduleItems by category without filtering by goal (単位4)', () => {
      const examSchedule = buildScheduleItemGoal(EXAM_GOAL)
      const readingSchedule = buildScheduleItemGoal(READING_GOAL)
      const workSchedule = buildScheduleItemGoal(WORK_GOAL)
      const result = resolveVisibleReportTargets(
        buildInput({ scheduleItems: [examSchedule, readingSchedule, workSchedule] }),
      )

      expect(result.examScheduleItemGoals).toEqual([examSchedule])
      expect(result.readingScheduleItemGoals).toEqual([readingSchedule])
      expect(result.workScheduleItemGoals).toEqual([workSchedule])
    })
  })

  describe('with the goal tab bar (2件以上の着手中目標)', () => {
    it('narrows the exam section to the selected goal', () => {
      const result = resolveVisibleReportTargets(
        buildInput({
          showGoalSelector: true,
          selectedGoal: EXAM_GOAL,
          goals: [EXAM_GOAL, OTHER_EXAM_GOAL],
          quotaItems: [EXAM_QUOTA, OTHER_EXAM_QUOTA],
        }),
      )

      expect(result.quotaItems).toEqual([EXAM_QUOTA])
      expect(result.diaryGoals).toEqual([EXAM_GOAL])
      expect(result.showExamSection).toBe(true)
      expect(result.showReadingSection).toBe(false)
      expect(result.showWorkSection).toBe(false)
    })

    it('narrows the reading section to the selected goal', () => {
      const result = resolveVisibleReportTargets(
        buildInput({ showGoalSelector: true, selectedGoal: READING_GOAL }),
      )

      expect(result.books).toEqual([BOOK])
      expect(result.showReadingSection).toBe(true)
      expect(result.showExamSection).toBe(false)
      expect(result.quotaItems).toEqual([])
      expect(result.diaryGoals).toEqual([])
    })

    it('narrows the work section to the selected goal', () => {
      const result = resolveVisibleReportTargets(
        buildInput({ showGoalSelector: true, selectedGoal: WORK_GOAL }),
      )

      expect(result.workAssignments).toEqual([WORK_ASSIGNMENT])
      expect(result.showWorkSection).toBe(true)
      expect(result.showReadingSection).toBe(false)
    })

    it('shows nothing while no tab is selected yet', () => {
      const result = resolveVisibleReportTargets(
        buildInput({ showGoalSelector: true, selectedGoal: undefined }),
      )

      expect(result.showExamSection).toBe(false)
      expect(result.showReadingSection).toBe(false)
      expect(result.showWorkSection).toBe(false)
      expect(result.books).toEqual([])
      expect(result.workAssignments).toEqual([])
    })

    it('hides the reading section when the selected reading goal has no book', () => {
      const result = resolveVisibleReportTargets(
        buildInput({ showGoalSelector: true, selectedGoal: READING_GOAL, readingBooks: [] }),
      )

      expect(result.showReadingSection).toBe(false)
    })

    it('hides the work section when the selected work goal has no assignment', () => {
      const result = resolveVisibleReportTargets(
        buildInput({ showGoalSelector: true, selectedGoal: WORK_GOAL, workAssignments: [] }),
      )

      expect(result.showWorkSection).toBe(false)
    })

    it('excludes books and assignments that belong to another goal', () => {
      const otherReadingGoal = buildGoal(5, 'READING')
      const otherBook = { id: 21, title: 'other-book' } as BookRead
      const result = resolveVisibleReportTargets(
        buildInput({
          showGoalSelector: true,
          selectedGoal: READING_GOAL,
          readingBooks: [
            { goal: READING_GOAL, book: BOOK },
            { goal: otherReadingGoal, book: otherBook },
          ],
        }),
      )

      expect(result.books).toEqual([BOOK])
    })

    it('narrows examScheduleItemGoals to the selected goal (単位4)', () => {
      const examSchedule = buildScheduleItemGoal(EXAM_GOAL)
      const otherExamSchedule = buildScheduleItemGoal(OTHER_EXAM_GOAL)
      const result = resolveVisibleReportTargets(
        buildInput({
          showGoalSelector: true,
          selectedGoal: EXAM_GOAL,
          goals: [EXAM_GOAL, OTHER_EXAM_GOAL],
          scheduleItems: [examSchedule, otherExamSchedule],
        }),
      )

      expect(result.examScheduleItemGoals).toEqual([examSchedule])
    })

    it('narrows readingScheduleItemGoals to the selected goal (単位4)', () => {
      const readingSchedule = buildScheduleItemGoal(READING_GOAL)
      const result = resolveVisibleReportTargets(
        buildInput({
          showGoalSelector: true,
          selectedGoal: READING_GOAL,
          scheduleItems: [readingSchedule],
        }),
      )

      expect(result.readingScheduleItemGoals).toEqual([readingSchedule])
    })

    it('narrows workScheduleItemGoals to the selected goal (単位4)', () => {
      const workSchedule = buildScheduleItemGoal(WORK_GOAL)
      const result = resolveVisibleReportTargets(
        buildInput({
          showGoalSelector: true,
          selectedGoal: WORK_GOAL,
          scheduleItems: [workSchedule],
        }),
      )

      expect(result.workScheduleItemGoals).toEqual([workSchedule])
    })

    it('shows no scheduleItems for any category while no tab is selected yet (単位4)', () => {
      const result = resolveVisibleReportTargets(
        buildInput({
          showGoalSelector: true,
          selectedGoal: undefined,
          scheduleItems: [
            buildScheduleItemGoal(EXAM_GOAL),
            buildScheduleItemGoal(READING_GOAL),
            buildScheduleItemGoal(WORK_GOAL),
          ],
        }),
      )

      expect(result.examScheduleItemGoals).toEqual([])
      expect(result.readingScheduleItemGoals).toEqual([])
      expect(result.workScheduleItemGoals).toEqual([])
    })
  })
})

describe('resolveVisibleReportTargets の presence', () => {
  it('reports a category as present when it has an active target, regardless of the selected tab', () => {
    // 選択中でないタブのカテゴリを「対象なし」と誤判定すると、1カテゴリ確定しただけで
    // 全カテゴリ確定済みとみなしてしまう（2026-09-05の不具合）。
    const result = resolveVisibleReportTargets(
      buildInput({ showGoalSelector: true, selectedGoal: READING_GOAL }),
    )

    expect(result.presence).toEqual({
      hasExamCategory: true,
      hasReadingCategory: true,
      hasWorkCategory: true,
    })
  })

  it('reports a category as absent when it has no active target', () => {
    const result = resolveVisibleReportTargets(
      buildInput({ goals: [], readingBooks: [], workAssignments: [] }),
    )

    expect(result.presence).toEqual({
      hasExamCategory: false,
      hasReadingCategory: false,
      hasWorkCategory: false,
    })
  })

  it('ignores goals that are not active when deciding the exam category presence', () => {
    const pausedExamGoal = { ...EXAM_GOAL, status: 'PAUSED' } as GoalRead
    const result = resolveVisibleReportTargets(buildInput({ goals: [pausedExamGoal] }))

    expect(result.presence.hasExamCategory).toBe(false)
    expect(result.diaryGoals).toEqual([])
  })
})
