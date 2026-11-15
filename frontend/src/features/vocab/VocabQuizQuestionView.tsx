import { useState } from 'react'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import type { VocabAnswerResult, VocabQuizMode, VocabQuizQuestion } from '../../api/vocab'

const FLASH_MODES: VocabQuizMode[] = ['FLASH_TERM_TO_MEANING', 'FLASH_MEANING_TO_TERM']
const CHOICE_MODES: VocabQuizMode[] = ['CHOICE_TERM_TO_MEANING', 'CHOICE_MEANING_TO_TERM']

export type VocabQuizAnswerPayload = {
  self_judged_correct?: boolean
  answer_text?: string
  selected_card_id?: number
}

/** 問題集の1問分の表示・解答入力。形式（カードめくり／入力式／4択）ごとにUIを分ける。 */
export function VocabQuizQuestionView({
  mode,
  question,
  lastResult,
  onSubmit,
  onNext,
}: {
  mode: VocabQuizMode
  question: VocabQuizQuestion
  lastResult: VocabAnswerResult | null
  onSubmit: (payload: VocabQuizAnswerPayload) => void
  onNext: () => void
}) {
  const [revealed, setRevealed] = useState(false)
  const [answerText, setAnswerText] = useState('')

  if (FLASH_MODES.includes(mode)) {
    return (
      <Card className="flex flex-col gap-3">
        <p className="text-lg text-text-primary">{question.prompt}</p>
        {!revealed ? (
          <Button onClick={() => setRevealed(true)}>{t('vocab.quiz.revealButton')}</Button>
        ) : (
          <>
            <p className="text-lg font-medium text-accent-muted-text">{question.reveal}</p>
            <div className="flex gap-2">
              <Button
                onClick={() => {
                  onSubmit({ self_judged_correct: true })
                  setRevealed(false)
                }}
              >
                {t('vocab.quiz.knewItButton')}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  onSubmit({ self_judged_correct: false })
                  setRevealed(false)
                }}
              >
                {t('vocab.quiz.didntKnowButton')}
              </Button>
            </div>
          </>
        )}
      </Card>
    )
  }

  if (CHOICE_MODES.includes(mode)) {
    return (
      <Card className="flex flex-col gap-3">
        <p className="text-lg text-text-primary">{question.prompt}</p>
        {lastResult ? (
          <VocabQuizResultAndNext result={lastResult} onNext={onNext} />
        ) : (
          <div className="flex flex-col gap-2">
            {question.options?.map((option) => (
              <Button
                key={option.card_id}
                variant="secondary"
                onClick={() => onSubmit({ selected_card_id: option.card_id })}
              >
                {option.text}
              </Button>
            ))}
          </div>
        )}
      </Card>
    )
  }

  // TYPED_MEANING_TO_TERM
  return (
    <Card className="flex flex-col gap-3">
      <p className="text-lg text-text-primary">{question.prompt}</p>
      {lastResult ? (
        <VocabQuizResultAndNext result={lastResult} onNext={onNext} />
      ) : (
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            onSubmit({ answer_text: answerText })
            setAnswerText('')
          }}
        >
          <Input
            value={answerText}
            onChange={(e) => setAnswerText(e.target.value)}
            aria-label={t('vocab.quiz.answerInputLabel')}
            autoFocus
          />
          <Button type="submit">{t('vocab.quiz.submitButton')}</Button>
        </form>
      )}
    </Card>
  )
}

function VocabQuizResultAndNext({
  result,
  onNext,
}: {
  result: VocabAnswerResult
  onNext: () => void
}) {
  return (
    <div className="flex flex-col gap-2 rounded-md bg-surface-muted p-3">
      <p className="text-sm font-medium text-text-primary">
        {result.is_correct ? t('vocab.quiz.correctLabel') : t('vocab.quiz.incorrectLabel')}
      </p>
      <Button onClick={onNext}>{t('vocab.quiz.nextButton')}</Button>
    </div>
  )
}
