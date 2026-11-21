import { describe, expect, it } from 'vitest'
import {
  resolveExamGoalIdForVocab,
  selectDiaryEntriesEligibleForVocabSuggestions,
} from './vocabSuggestionEligibility'
import type { components } from '../../types/api.d.ts'

type DiaryEntryRead = components['schemas']['DiaryEntryRead']

function entry(overrides: Partial<DiaryEntryRead> = {}): DiaryEntryRead {
  return {
    goal_id: 1,
    goal_name: 'goal',
    diary_body: '',
    diary_learned: 'TCPを学んだ',
    ...overrides,
  }
}

describe('selectDiaryEntriesEligibleForVocabSuggestions', () => {
  const examGoalIds = new Set([1, 2])

  it('excludes entries with a null goal id', () => {
    const result = selectDiaryEntriesEligibleForVocabSuggestions(
      [entry({ goal_id: null })],
      examGoalIds,
    )
    expect(result).toEqual([])
  })

  it('excludes entries whose goal id is not in examGoalIds', () => {
    const result = selectDiaryEntriesEligibleForVocabSuggestions(
      [entry({ goal_id: 999 })],
      examGoalIds,
    )
    expect(result).toEqual([])
  })

  it('excludes entries with blank or whitespace-only learned text', () => {
    const result = selectDiaryEntriesEligibleForVocabSuggestions(
      [entry({ diary_learned: '' }), entry({ diary_learned: '   ' })],
      examGoalIds,
    )
    expect(result).toEqual([])
  })

  it('includes entries whose goal id is in examGoalIds with non-blank learned text', () => {
    const eligible = entry({ goal_id: 2 })
    const result = selectDiaryEntriesEligibleForVocabSuggestions([eligible], examGoalIds)
    expect(result).toEqual([eligible])
  })
})

describe('resolveExamGoalIdForVocab', () => {
  const examGoalIds = new Set([1, 2])

  it('returns the selected goal id when the selected goal is EXAM', () => {
    const result = resolveExamGoalIdForVocab({
      selectedGoal: { id: 1, category: 'EXAM' },
      diaryEntries: [],
      examGoalIds,
    })
    expect(result).toBe(1)
  })

  it('falls back to the goal with a learned diary entry when the selected goal is not EXAM', () => {
    const result = resolveExamGoalIdForVocab({
      selectedGoal: { id: 5, category: 'READING' },
      diaryEntries: [entry({ goal_id: 2 })],
      examGoalIds,
    })
    expect(result).toBe(2)
  })

  it('falls back to the first exam goal id when there is no selected goal or diary entry', () => {
    const result = resolveExamGoalIdForVocab({
      selectedGoal: undefined,
      diaryEntries: [],
      examGoalIds,
    })
    expect(result).toBe(1)
  })

  it('returns null when there is no selected exam goal, diary entry, or exam goal id', () => {
    const result = resolveExamGoalIdForVocab({
      selectedGoal: undefined,
      diaryEntries: [],
      examGoalIds: new Set(),
    })
    expect(result).toBeNull()
  })
})
