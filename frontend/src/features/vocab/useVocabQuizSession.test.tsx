/** useVocabQuizSession の回帰テスト。カバレッジ閾値の対象外（vite.config.ts
 * `src/**\/use*.ts` 除外）だが、FLASH形式は即時に次の問題へ進み、入力式・4択形式は
 * 結果を表示してから利用者の「次へ」操作で進むという非自明な分岐を持つため、
 * OPERATIONS.md「フロントエンドのテストとカバレッジ」の方針に沿って直接テストする。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useVocabQuizSession } from './useVocabQuizSession'

const answerVocabCard = vi.hoisted(() => vi.fn())
const checkVocabCard = vi.hoisted(() => vi.fn())
const startVocabQuizSession = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({ answerVocabCard, checkVocabCard, startVocabQuizSession }))

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return renderHook(() => useVocabQuizSession(1), { wrapper })
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('useVocabQuizSession の開始', () => {
  it('sets the mode and questions from the started session', async () => {
    startVocabQuizSession.mockResolvedValue({
      questions: [{ card_id: 1, prompt: 'A' }],
      excluded_count: 0,
    })
    const { result } = setup()

    await act(async () => {
      result.current.start({ mode: 'FLASH_TERM_TO_MEANING', filter: 'ALL', order: 'RANDOM', question_count: 1 })
    })

    expect(result.current.mode).toBe('FLASH_TERM_TO_MEANING')
    expect(result.current.questions).toHaveLength(1)
    expect(result.current.index).toBe(0)
  })
})

describe('useVocabQuizSession の解答進行', () => {
  it('advances immediately for FLASH modes without setting lastResult', async () => {
    startVocabQuizSession.mockResolvedValue({
      questions: [
        { card_id: 1, prompt: 'A' },
        { card_id: 2, prompt: 'B' },
      ],
      excluded_count: 0,
    })
    answerVocabCard.mockResolvedValue({ is_correct: true })
    const { result } = setup()
    await act(async () => {
      result.current.start({ mode: 'FLASH_TERM_TO_MEANING', filter: 'ALL', order: 'RANDOM', question_count: 2 })
    })

    await act(async () => {
      result.current.answer({ self_judged_correct: true })
    })

    expect(result.current.index).toBe(1)
    expect(result.current.lastResult).toBeNull()
    expect(result.current.summary.correctCount).toBe(1)
  })

  it('shows the result without advancing for non-FLASH modes until next() is called', async () => {
    startVocabQuizSession.mockResolvedValue({
      questions: [{ card_id: 1, prompt: 'A' }],
      excluded_count: 0,
    })
    answerVocabCard.mockResolvedValue({ is_correct: false })
    const { result } = setup()
    await act(async () => {
      result.current.start({ mode: 'TYPED_MEANING_TO_TERM', filter: 'ALL', order: 'RANDOM', question_count: 1 })
    })

    await act(async () => {
      result.current.answer({ answer_text: '違う答え' })
    })

    expect(result.current.index).toBe(0)
    expect(result.current.lastResult).toEqual({ is_correct: false })

    act(() => {
      result.current.next()
    })

    expect(result.current.index).toBe(1)
    expect(result.current.lastResult).toBeNull()
  })

  it('does nothing when there is no current question or mode', () => {
    const { result } = setup()

    act(() => {
      result.current.answer({ self_judged_correct: true })
    })

    expect(answerVocabCard).not.toHaveBeenCalled()
  })
})

describe('useVocabQuizSession のまとめてチェック', () => {
  it('checks every given card id', async () => {
    checkVocabCard.mockResolvedValue({})
    const { result } = setup()

    await act(async () => {
      result.current.checkWrongCards([1, 2])
    })

    expect(checkVocabCard).toHaveBeenCalledWith(1, true)
    expect(checkVocabCard).toHaveBeenCalledWith(2, true)
  })
})
