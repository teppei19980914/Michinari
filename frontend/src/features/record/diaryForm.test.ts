import { describe, expect, it } from 'vitest'
import {
  buildDiaryEntriesPayload,
  combineDiaryBody,
  filterWrittenDiaryEntries,
  getDiaryQuestions,
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
    expect(values[1]).toEqual({ diaryLearned: '', questionAnswers: ['', ''], freeText: '' })
  })

  it('prefills the free-write field from an existing diary entry (no reverse-parsing into questions)', () => {
    const existing: DiaryEntryRead = {
      goal_id: 1,
      goal_name: '目標A',
      diary_body: '今日は頑張った',
      diary_learned: '学び',
    }
    const values = initDiaryFormValues([makeGoal(1, '目標A')], [existing])
    expect(values[1]).toEqual({
      diaryLearned: '学び',
      questionAnswers: ['', ''],
      freeText: '今日は頑張った',
    })
  })

  it('treats null diary text as an empty string', () => {
    const existing: DiaryEntryRead = {
      goal_id: 1,
      goal_name: '目標A',
      diary_body: null,
      diary_learned: null,
    }
    const values = initDiaryFormValues([makeGoal(1, '目標A')], [existing])
    expect(values[1]).toEqual({ diaryLearned: '', questionAnswers: ['', ''], freeText: '' })
  })

  it('ignores entries with no goal_id (historical fallback rows)', () => {
    const orphan: DiaryEntryRead = {
      goal_id: null,
      goal_name: null,
      diary_body: '帰属先不明の日記',
      diary_learned: null,
    }
    const values = initDiaryFormValues([makeGoal(1, '目標A')], [orphan])
    expect(values[1]).toEqual({ diaryLearned: '', questionAnswers: ['', ''], freeText: '' })
  })
})

describe('hasAnyDiaryInput', () => {
  it('is false when every goal is untouched', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryLearned: '', questionAnswers: ['', ''], freeText: '' },
    }
    expect(hasAnyDiaryInput(values)).toBe(false)
  })

  it('is true once a goal has learned text', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryLearned: '学び', questionAnswers: ['', ''], freeText: '' },
    }
    expect(hasAnyDiaryInput(values)).toBe(true)
  })

  it('is true once a goal has a question answer', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryLearned: '', questionAnswers: ['回答', ''], freeText: '' },
    }
    expect(hasAnyDiaryInput(values)).toBe(true)
  })

  it('is true once a goal has free-write text', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryLearned: '', questionAnswers: ['', ''], freeText: '自由記述' },
    }
    expect(hasAnyDiaryInput(values)).toBe(true)
  })
})

describe('combineDiaryBody', () => {
  it('returns the free-write text as-is when no question is answered (backward compatibility)', () => {
    expect(
      combineDiaryBody({ diaryLearned: '', questionAnswers: ['', ''], freeText: '今日は頑張った' }),
    ).toBe('今日は頑張った')
  })

  it('labels answered questions and appends the free-write text', () => {
    const [question1] = getDiaryQuestions()
    expect(
      combineDiaryBody({
        diaryLearned: '',
        questionAnswers: ['回答1', ''],
        freeText: '自由記述',
      }),
    ).toBe(`【${question1}】\n回答1\n\n自由記述`)
  })

  it('returns an empty string when nothing is filled in', () => {
    expect(combineDiaryBody({ diaryLearned: '', questionAnswers: ['', ''], freeText: '' })).toBe('')
  })
})

describe('buildDiaryEntriesPayload', () => {
  it('excludes goals with no input', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryLearned: '', questionAnswers: ['', ''], freeText: '' },
      2: { diaryLearned: '学び', questionAnswers: ['', ''], freeText: '今日は頑張った' },
    }
    expect(buildDiaryEntriesPayload(values)).toEqual([
      { goal_id: 2, diary_body: '今日は頑張った', diary_learned: '学び' },
    ])
  })

  it('includes a goal when only the learned field has text', () => {
    const values: Record<number, DiaryFormValue> = {
      1: { diaryLearned: '学び', questionAnswers: ['', ''], freeText: '' },
    }
    expect(buildDiaryEntriesPayload(values)).toEqual([
      { goal_id: 1, diary_body: '', diary_learned: '学び' },
    ])
  })
})

describe('filterWrittenDiaryEntries', () => {
  function buildEntry(overrides: Partial<DiaryEntryRead>): DiaryEntryRead {
    return {
      goal_id: 1,
      goal_name: 'goal',
      diary_body: null,
      diary_learned: null,
      ...overrides,
    }
  }

  it('keeps an entry that has a body', () => {
    const entry = buildEntry({ diary_body: 'body' })
    expect(filterWrittenDiaryEntries([entry])).toEqual([entry])
  })

  it('keeps an entry that only has the learned field', () => {
    const entry = buildEntry({ diary_learned: 'learned' })
    expect(filterWrittenDiaryEntries([entry])).toEqual([entry])
  })

  it('drops entries that were finalized without writing anything', () => {
    // 日記の枠は目標ごとに作られるため、何も書かずに確定した目標の分は空で保存される。
    expect(filterWrittenDiaryEntries([buildEntry({}), buildEntry({ diary_body: '' })])).toEqual([])
  })
})
