import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  answerVocabCard,
  checkVocabCard,
  completeVocabQuizSession,
  startVocabQuizSession,
  type VocabAnswerResult,
  type VocabQuizMode,
  type VocabQuizQuestion,
} from '../../api/vocab'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { useMilestoneCelebrationQueue } from '../milestone/useMilestoneCelebrationQueue'
import type { VocabQuizSessionParams } from './VocabQuizSetupForm'
import type { VocabQuizAnswerPayload } from './VocabQuizQuestionView'
import { buildSessionSummary, nextIndex, type VocabAnswerRecord } from './vocabQuizProgress'

//: 自己採点（カードをめくる）方式のモード。SITUATIONカードのFLASH_SITUATIONも同じ採点
//: 方法のため含める（開発Todo_単語帳_v1.0 要件F F-D24）。
const FLASH_MODES: VocabQuizMode[] = [
  'FLASH_TERM_TO_MEANING',
  'FLASH_MEANING_TO_TERM',
  'FLASH_SITUATION',
]

/** 出題セッションの状態と操作をまとめたフック（VocabQuizPageが100行制限に収まるよう分割、
 * CODING_RULES.md「保守性（複雑度）」）。セッションを終えたときの単語帳の習得用語数の
 * 節目判定（開発Todo_単語帳_v1.0 要件E E-U3）もここで行う。`goalId`はデッキ取得が
 * 終わるまで`undefined`（呼び出し元のGET /vocab-decks/{deckId}が先に解決する必要がある）。 */
export function useVocabQuizSession(deckId: number, goalId: number | undefined) {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<VocabQuizMode | null>(null)
  const [questions, setQuestions] = useState<VocabQuizQuestion[]>([])
  const [index, setIndex] = useState(0)
  const [results, setResults] = useState<VocabAnswerRecord[]>([])
  const [lastResult, setLastResult] = useState<VocabAnswerResult | null>(null)
  const milestoneQueue = useMilestoneCelebrationQueue()

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
    mutationFn: ({
      cardId,
      mode: answerMode,
      payload,
    }: {
      cardId: number
      mode: VocabQuizMode
      payload: VocabQuizAnswerPayload
    }) => answerVocabCard(cardId, { mode: answerMode, ...payload }),
  })
  const checkMutation = useMutation({
    mutationFn: (cardIds: number[]) => Promise.all(cardIds.map((id) => checkVocabCard(id, true))),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vocabCards(deckId) }),
  })
  const completeMutation = useMutation({
    mutationFn: () => completeVocabQuizSession(deckId),
    onSuccess: () => {
      void milestoneQueue.checkGoal(goalId, 'EXAM')
    },
  })

  const currentQuestion = questions[index]
  const isSessionDone = mode != null && questions.length > 0 && index >= questions.length

  // セッション終了への遷移1回だけ呼ぶ（新しいセッション開始でindex/questionsがリセットされ、
  // 次に終えたときも再度false→trueの遷移として捉えられる）。
  useEffect(() => {
    if (isSessionDone) {
      completeMutation.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSessionDone])

  const handleAnswer = (payload: VocabQuizAnswerPayload) => {
    if (!currentQuestion || !mode) return
    //: その問題の実際の出題形式（開発Todo_単語帳_v1.0 要件F F-D7）。「両方」選択時は
    //: SITUATIONカードがFLASH_SITUATIONになるため、セッション単位のmodeとは異なりうる。
    const answerMode = currentQuestion.mode
    answerMutation.mutate(
      { cardId: currentQuestion.card_id, mode: answerMode, payload },
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
          if (FLASH_MODES.includes(answerMode)) {
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
    milestone: milestoneQueue.current,
    dismissMilestone: milestoneQueue.dismissCurrent,
  }
}
