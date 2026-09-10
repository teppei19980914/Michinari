import { describe, expect, it } from 'vitest'
import {
  buildDiaryEntriesPayload,
  hasAnyDiaryInput,
  initDiaryFormValues,
  type DiaryFormValue,
} from './diaryForm'
import type { DiaryEntryRead } from '../../api/records'
import type { GoalRead } from '../../api/goals'

function makeGoal(id: number, name: string): GoalRead {
  return {
    id,
    category: 'EXAM',
    name,
    start_date: '2026-01-01',
    status: 'ACTIVE',
    memo: null,
    activated_at: null,
    closed_at: null,
    archived_at: null,
  }
}

describe('initDiaryFormValues', () => {
  it('defaults to empty strings when no existing entry for a goal', () => {
    const values = initDiaryFormValues([makeGoal(1, '目標A')], [])
    expect(values[1]).toEqual({ diaryBody: '', diaryLearned: '' })
  })

  it('prefills from an existing diary entry', () => {
    const existing: DiaryEntryRead = {
      goal_id: 1,
      goal_name: '目標A',
      diary_body: '今日は頑張った',
      diary_learned: '学び',
    }
    const values = initDiaryFormValues([makeGoal(1, '目標A')], [existing])
    expect(values[1]).toEqual({ diaryBody: '今日は頑張った', diaryLearned: '学び' })
  })

  it('treats null diary text as an empty string', () => {
    const existing: DiaryEntryRead = {
      goal_id: 1,
      goal_name: '目標A',
      diary_body: null,
      diary_learned: null,
    }
    const values = initDiaryFormValues([makeGoal(1, '目標A')], [existing])
    expect(values[1]).toEqual({ diaryBody: '', diaryLearned: '' })
  })

  it('ignores entries with no goal_id (historical fallback rows)', () => {
    const orphan: DiaryEntryRead = {
      goal_id: null,
      goal_name: null,
      diary_body: '帰属先不明の日記',
      diary_learned: null,
    }
    const values = initDiaryFormValues([makeGoal(1, '目標A')], [orphan])
    expect(values[1]).toEqual({ diaryBody: '', diaryLearned: '' })
  })
})

describe('hasAnyDiaryInput', () => {
  it('is false when every goal is untouched', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryBody: '', diaryLearned: '' },
    }
    expect(hasAnyDiaryInput(values)).toBe(false)
  })

  it('is true once a goal has body or learned text', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryBody: '', diaryLearned: '学び' },
    }
    expect(hasAnyDiaryInput(values)).toBe(true)
  })
})

describe('buildDiaryEntriesPayload', () => {
  it('excludes goals with no input', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryBody: '', diaryLearned: '' },
      2: { diaryBody: '今日は頑張った', diaryLearned: '学び' },
    }
    expect(buildDiaryEntriesPayload(values)).toEqual([
      { goal_id: 2, diary_body: '今日は頑張った', diary_learned: '学び' },
    ])
  })

  it('includes a goal when only one of the two fields has text', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryBody: '', diaryLearned: '学び' },
    }
    expect(buildDiaryEntriesPayload(values)).toEqual([
      { goal_id: 1, diary_body: '', diary_learned: '学び' },
    ])
  })
})
