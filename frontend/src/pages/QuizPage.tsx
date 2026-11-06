import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { t } from '../locales/t'
import { Card } from '../components/Card'
import { apiErrorMessage } from '../api/client'
import { getTodayQuiz } from '../api/quiz'
import { QuizSession } from '../features/quiz/QuizSession'
import { QUERY_KEYS } from '../constants/queryKeys'
import { ROUTE_PATTERNS } from '../constants/routes'

/** 復習クイズの出題画面（仕様書6.1.6）。今日出題すべきクイズを1問ずつ解答する。 */
export function QuizPage() {
  const [finished, setFinished] = useState(false)
  const query = useQuery({ queryKey: QUERY_KEYS.todayQuiz(), queryFn: getTodayQuiz })

  if (query.isLoading) {
    return <p className="p-6 text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (query.isError) {
    return <p className="p-6 text-sm text-danger-text">{apiErrorMessage(query.error)}</p>
  }

  const questions = query.data ?? []

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-3 p-4">
      <Link className="text-sm text-accent-muted-text underline" to={ROUTE_PATTERNS.dashboard}>
        {t('quiz.backToDashboard')}
      </Link>
      {finished || questions.length === 0 ? (
        <Card>
          <p className="text-sm text-text-primary">{t('quiz.completedTitle')}</p>
        </Card>
      ) : (
        <QuizSession questions={questions} onFinished={() => setFinished(true)} />
      )}
    </div>
  )
}
