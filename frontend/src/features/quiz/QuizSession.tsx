import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { MarkdownText } from '../../components/MarkdownText'
import { apiErrorMessage } from '../../api/client'
import { answerQuiz, type QuizAnswerResult, type QuizQuestion } from '../../api/quiz'
import { ROUTES } from '../../constants/routes'
import { isLastQuestion, nextIndex } from './quizProgress'

type QuizSessionProps = {
  questions: QuizQuestion[]
  onFinished: () => void
}

/** 出題前の出所表示（テーマ名、または単語帳名）。出所（テーマ／単語帳）に応じて切り替える
 * （開発Todo_単語帳_v1.0 要件B）。 */
function SourceHeader({ question }: { question: QuizQuestion }) {
  if (question.source === 'vocab') {
    return <p className="text-xs text-text-faint">{t('quiz.vocabSourceHeader', { deckName: question.vocab_deck_name ?? '' })}</p>
  }
  return <p className="text-xs text-text-faint">{question.theme_name}</p>
}

/** 解答後の出典表示。単語帳由来なら「単語帳で確認する」リンクも表示する（開発Todo_単語帳_v1.0 要件B）。 */
function CitationFooter({ result }: { result: QuizAnswerResult }) {
  if (result.source === 'vocab') {
    return (
      <div className="flex flex-col gap-1">
        <p className="text-xs text-text-faint">
          {t('quiz.vocabCitationLabel', { deckName: result.vocab_deck_name ?? '' })}
        </p>
        {result.vocab_deck_id != null && (
          <Link
            className="text-xs text-accent-muted-text underline"
            to={ROUTES.vocabDeck(result.vocab_deck_id)}
          >
            {t('quiz.viewInVocabDeckLink')}
          </Link>
        )}
      </div>
    )
  }
  return (
    <p className="text-xs text-text-faint">
      {t('quiz.citationLabel', { date: result.citation_date ?? '' })}
    </p>
  )
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
      <SourceHeader question={question} />
      <h2 className="whitespace-pre-wrap text-base font-medium text-text-primary">
        {question.question_text}
      </h2>
      <div className="flex flex-col gap-2">
        {question.choices.map((choice, index) => (
          <Button
            key={index}
            variant={result && index === result.correct_choice_index ? 'primary' : 'secondary'}
            disabled={result !== null || answerMutation.isPending}
            onClick={() => answerMutation.mutate(index)}
          >
            <span className="whitespace-pre-wrap">{choice}</span>
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
          <CitationFooter result={result} />
          <div className="flex justify-end">
            <Button onClick={handleNext}>{t('quiz.nextButton')}</Button>
          </div>
        </div>
      )}
    </Card>
  )
}
