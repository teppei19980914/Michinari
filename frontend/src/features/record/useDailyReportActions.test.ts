/** `triggerVocabTermSuggestions`（開発Todo_単語帳_v1.0 要件D D-U4・D-D18）の振る舞いを
 * 固定する。確定成功後に日記（学んだこと）のある目標ごとに単語帳の用語提案を作るが、
 * AI未設定・単語帳0件のときは呼ばない、失敗しても確定成功自体を妨げない「静かな失敗」と
 * する、という非自明な分岐を持つため、`src/**\/use*.ts`の閾値除外方針（vite.config.ts）
 * でも直接テストを書く対象とする。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { triggerVocabTermSuggestions } from './useDailyReportActions'
import type { DailyRecordRead } from '../../api/records'
import type { VocabDeck } from '../../api/vocab'

const getVocabDecks = vi.hoisted(() => vi.fn())
const generateVocabTermSuggestions = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({ getVocabDecks, generateVocabTermSuggestions }))

const TARGET_DATE = '2026-11-20'
const EXAM_GOAL_IDS = new Set([1, 2])

function makeDeck(id: number, goalId: number): VocabDeck {
  return {
    id,
    goal_id: goalId,
    name: 'デッキ',
    description: null,
    use_in_ai: true,
    display_order: 0,
    card_count: 0,
    mastered_card_count: 0,
    term_card_count: 0,
    term_mastered_card_count: 0,
    situation_card_count: 0,
    situation_mastered_card_count: 0,
    session_default_questions: 10,
    session_max_questions: 100,
  }
}

function buildRecord(
  diaryEntries: DailyRecordRead['diary_entries'],
): DailyRecordRead {
  return {
    record_date: TARGET_DATE,
    exam_record_state: 'REPORTED',
    exam_reported_at: '2026-11-20T00:00:00Z',
    reading_record_state: null,
    reading_reported_at: null,
    work_record_state: null,
    work_reported_at: null,
    exam_mood: null,
    reading_mood: null,
    work_mood: null,
    diary_entries: diaryEntries,
    study_logs: [],
    reading_logs: [],
    work_logs: [],
    comments: [],
    chat_messages: [],
  }
}

function flushMicrotasks(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('triggerVocabTermSuggestions', () => {
  it('does nothing when AI is not configured', async () => {
    const queryClient = new QueryClient()
    const record = buildRecord([
      { goal_id: 1, goal_name: 'goal', diary_body: '', diary_learned: 'TCPを学んだ' },
    ])

    triggerVocabTermSuggestions(record, TARGET_DATE, false, queryClient, EXAM_GOAL_IDS)
    await flushMicrotasks()

    expect(getVocabDecks).not.toHaveBeenCalled()
  })

  it('skips entries without a goal id or with blank learned text', async () => {
    const queryClient = new QueryClient()
    const record = buildRecord([
      { goal_id: null, goal_name: null, diary_body: '', diary_learned: 'x' },
      { goal_id: 1, goal_name: 'goal', diary_body: '', diary_learned: '   ' },
    ])

    triggerVocabTermSuggestions(record, TARGET_DATE, true, queryClient, EXAM_GOAL_IDS)
    await flushMicrotasks()

    expect(getVocabDecks).not.toHaveBeenCalled()
  })

  it('skips entries whose goal id is not in examGoalIds', async () => {
    const queryClient = new QueryClient()
    const record = buildRecord([
      { goal_id: 999, goal_name: 'non-exam-goal', diary_body: '', diary_learned: 'TCPを学んだ' },
    ])

    triggerVocabTermSuggestions(record, TARGET_DATE, true, queryClient, EXAM_GOAL_IDS)
    await flushMicrotasks()

    expect(getVocabDecks).not.toHaveBeenCalled()
  })

  it('does not generate suggestions when the goal has no vocab decks', async () => {
    getVocabDecks.mockResolvedValue([])
    const queryClient = new QueryClient()
    const record = buildRecord([
      { goal_id: 1, goal_name: 'goal', diary_body: '', diary_learned: 'TCPを学んだ' },
    ])

    triggerVocabTermSuggestions(record, TARGET_DATE, true, queryClient, EXAM_GOAL_IDS)
    await flushMicrotasks()

    expect(getVocabDecks).toHaveBeenCalledWith(1)
    expect(generateVocabTermSuggestions).not.toHaveBeenCalled()
  })

  it('generates suggestions and invalidates the suggestions query when the goal has decks', async () => {
    getVocabDecks.mockResolvedValue([makeDeck(10, 1)])
    generateVocabTermSuggestions.mockResolvedValue({ suggestions: [], default_deck_id: 10 })
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const record = buildRecord([
      { goal_id: 1, goal_name: 'goal', diary_body: '', diary_learned: 'TCPを学んだ' },
    ])

    triggerVocabTermSuggestions(record, TARGET_DATE, true, queryClient, EXAM_GOAL_IDS)
    await flushMicrotasks()

    expect(generateVocabTermSuggestions).toHaveBeenCalledWith(1, TARGET_DATE)
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: QUERY_KEYS.vocabTermSuggestions(1, TARGET_DATE),
    })
  })

  it('silently swallows failures without throwing (D-D18)', async () => {
    getVocabDecks.mockRejectedValue(new Error('network error'))
    const queryClient = new QueryClient()
    const record = buildRecord([
      { goal_id: 1, goal_name: 'goal', diary_body: '', diary_learned: 'TCPを学んだ' },
    ])

    expect(() =>
      triggerVocabTermSuggestions(record, TARGET_DATE, true, queryClient, EXAM_GOAL_IDS),
    ).not.toThrow()
    await flushMicrotasks()
  })

  it('calls getVocabDecks independently (in parallel) for multiple goals', async () => {
    getVocabDecks.mockResolvedValue([])
    const queryClient = new QueryClient()
    const record = buildRecord([
      { goal_id: 1, goal_name: 'goal1', diary_body: '', diary_learned: 'TCPを学んだ' },
      { goal_id: 2, goal_name: 'goal2', diary_body: '', diary_learned: 'UDPを学んだ' },
    ])

    triggerVocabTermSuggestions(record, TARGET_DATE, true, queryClient, EXAM_GOAL_IDS)
    await flushMicrotasks()

    expect(getVocabDecks).toHaveBeenCalledWith(1)
    expect(getVocabDecks).toHaveBeenCalledWith(2)
    expect(getVocabDecks).toHaveBeenCalledTimes(2)
  })
})
