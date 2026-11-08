import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { t } from '../locales/t'
import { Card } from '../components/Card'
import { AiUnconfiguredNotice } from '../components/AiUnconfiguredNotice'
import { apiErrorMessage } from '../api/client'
import { getTodayQuiz } from '../api/quiz'
import { useAiConfigured } from '../hooks/useAiConfigured'
import { QuizSession } from '../features/quiz/QuizSession'
import { QUERY_KEYS } from '../constants/queryKeys'
import { ROUTE_PATTERNS } from '../constants/routes'

/** 復習クイズの出題画面（仕様書6.1.6）。今日出題すべきクイズを1問ずつ解答する。
 *
 * クイズの生成にはAIが必須のため、AI未設定の間は機能の説明と設定への案内のみを表示する
 * （要件6、目標相談チャット等と同じ`useAiConfigured`パターン）。 */
export function QuizPage() {
  const [finished, setFinished] = useState(false)
  const aiConfigured = useAiConfigured()
  // GET /quiz/todayはDB読み取りのみ（AI呼び出しを伴わない）ため、AI未設定時でも
  // 発行して構わない。取得結果は未設定時の表示分岐（下記）では使わないだけ。
  const query = useQuery({ queryKey: QUERY_KEYS.todayQuiz(), queryFn: getTodayQuiz })

  if (!aiConfigured) {
    return (
      <div className="mx-auto flex max-w-xl flex-col gap-3 p-4">
        <Link className="text-sm text-accent-muted-text underline" to={ROUTE_PATTERNS.dashboard}>
          {t('quiz.backToDashboard')}
        </Link>
        <p className="text-sm text-text-primary">{t('quiz.aiRequiredDescription')}</p>
        <AiUnconfiguredNotice />
      </div>
    )
  }

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
