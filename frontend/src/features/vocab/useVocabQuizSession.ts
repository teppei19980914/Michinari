import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  answerVocabCard,
  checkVocabCard,
  startVocabQuizSession,
  type VocabAnswerResult,
  type VocabQuizMode,
  type VocabQuizQuestion,
} from '../../api/vocab'
import { QUERY_KEYS } from '../../constants/queryKeys'
import type { VocabQuizSessionParams } from './VocabQuizSetupForm'
import type { VocabQuizAnswerPayload } from './VocabQuizQuestionView'
import { buildSessionSummary, nextIndex, type VocabAnswerRecord } from './vocabQuizProgress'

const FLASH_MODES: VocabQuizMode[] = ['FLASH_TERM_TO_MEANING', 'FLASH_MEANING_TO_TERM']

/** 出題セッションの状態と操作をまとめたフック（VocabQuizPageが100行制限に収まるよう分割、
 * CODING_RULES.md「保守性（複雑度）」）。 */
export function useVocabQuizSession(deckId: number) {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<VocabQuizMode | null>(null)
  const [questions, setQuestions] = useState<VocabQuizQuestion[]>([])
  const [index, setIndex] = useState(0)
  const [results, setResults] = useState<VocabAnswerRecord[]>([])
  const [lastResult, setLastResult] = useState<VocabAnswerResult | null>(null)

  const startMutation = useMutation({
    mutationFn: (params: VocabQuizSessionParams) => startVocabQuizSession(deckId, params),
    onSuccess: (session, params) => {
      setMode(params.mode)
      setQuestions(session.questions)
      setIndex(0)
      setResults([])
      setLastResult(null)
    },
  })
  const answerMutation = useMutation({
    mutationFn: ({ cardId, payload }: { cardId: number; payload: VocabQuizAnswerPayload }) =>
      answerVocabCard(cardId, { mode: mode as VocabQuizMode, ...payload }),
  })
  const checkMutation = useMutation({
    mutationFn: (cardIds: number[]) => Promise.all(cardIds.map((id) => checkVocabCard(id, true))),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabCards(deckId) }),
  })

  const currentQuestion = questions[index]

  const handleAnswer = (payload: VocabQuizAnswerPayload) => {
    if (!currentQuestion || !mode) return
    answerMutation.mutate(
      { cardId: currentQuestion.card_id, payload },
      {
        onSuccess: (result) => {
          setResults((prev) => [
            ...prev,
            {
              cardId: currentQuestion.card_id,
              term: currentQuestion.prompt,
              isCorrect: result.is_correct,
            },
          ])
          if (FLASH_MODES.includes(mode)) {
            setIndex(nextIndex(index))
          } else {
            setLastResult(result)
          }
        },
      },
    )
  }
  const handleNext = () => {
    setLastResult(null)
    setIndex(nextIndex(index))
  }

  return {
    mode,
    questions,
    index,
    currentQuestion,
    lastResult,
    summary: buildSessionSummary(results),
    isChecking: checkMutation.isPending,
    start: (params: VocabQuizSessionParams) => startMutation.mutate(params),
    answer: handleAnswer,
    next: handleNext,
    checkWrongCards: (cardIds: number[]) => checkMutation.mutate(cardIds),
  }
}
