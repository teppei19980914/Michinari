import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { MarkdownText } from '../../components/MarkdownText'
import { apiErrorMessage } from '../../api/client'
import { answerQuiz, type QuizAnswerResult, type QuizQuestion } from '../../api/quiz'
import { isLastQuestion, nextIndex } from './quizProgress'

type QuizSessionProps = {
  questions: QuizQuestion[]
  onFinished: () => void
}

/** 復習クイズの出題（仕様書6.1.6）。1問ずつ解答し、正誤・解説・出典を表示して次へ進む。 */
export function QuizSession({ questions, onFinished }: QuizSessionProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [result, setResult] = useState<QuizAnswerResult | null>(null)
  const question = questions[currentIndex]

  const answerMutation = useMutation({
    mutationFn: (choiceIndex: number) => answerQuiz(question.id, choiceIndex),
    onSuccess: setResult,
  })

  const handleNext = () => {
    setResult(null)
    if (isLastQuestion(currentIndex, questions.length)) {
      onFinished()
    } else {
      setCurrentIndex(nextIndex(currentIndex))
    }
  }

  return (
    <Card className="flex flex-col gap-3">
      <p className="text-xs text-text-faint">
        {t('quiz.progressLabel', { current: currentIndex + 1, total: questions.length })}
      </p>
      <p className="text-xs text-text-faint">{question.theme_name}</p>
      <h2 className="text-base font-medium text-text-primary">{question.question_text}</h2>
      <div className="flex flex-col gap-2">
        {question.choices.map((choice, index) => (
          <Button
            key={index}
            variant={result && index === result.correct_choice_index ? 'primary' : 'secondary'}
            disabled={result !== null || answerMutation.isPending}
            onClick={() => answerMutation.mutate(index)}
          >
            {choice}
          </Button>
        ))}
      </div>
      {answerMutation.isError && (
        <p className="text-sm text-danger-text">{apiErrorMessage(answerMutation.error)}</p>
      )}
      {result && (
        <div className="flex flex-col gap-2 rounded-md bg-surface-muted p-3">
          <p className="text-sm font-medium text-text-primary">
            {result.is_correct ? t('quiz.correctLabel') : t('quiz.incorrectLabel')}
          </p>
          <MarkdownText text={result.explanation} className="text-sm text-text-secondary" />
          <p className="text-xs text-text-faint">
            {t('quiz.citationLabel', { date: result.citation_date })}
          </p>
          <div className="flex justify-end">
            <Button onClick={handleNext}>{t('quiz.nextButton')}</Button>
          </div>
        </div>
      )}
    </Card>
  )
}
