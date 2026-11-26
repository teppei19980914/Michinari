import { Navigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { apiErrorMessage } from '../api/client'
import { getVocabDecks } from '../api/vocab'
import { QUERY_KEYS } from '../constants/queryKeys'

/** 全画面ヘッダー「単語帳」タブ→目標クリックの直接の遷移先（開発Todo_単語帳_出題導線改修
 * _v1.0 U6・D6）。単語帳（デッキ）はユーザーに見せず1目標につき常に1件のため、目標詳細
 * 画面を経由せず、ここでgoalIdからdeckIdを解決して問題出題内容設定画面（`VocabQuizPage`）
 * へ直接中継する。 */
export function VocabGoalQuizRedirectPage() {
  const { goalId: goalIdParam } = useParams<{ goalId: string }>()
  const goalId = Number(goalIdParam)

  const decksQuery = useQuery({
    queryKey: QUERY_KEYS.vocabDecks(goalId),
    queryFn: () => getVocabDecks(goalId),
  })

  if (decksQuery.isLoading) {
    return <p className="p-6 text-sm text-text-faint">{t('common.loading')}</p>
  }
  const deck = decksQuery.data?.[0]
  if (decksQuery.isError || !deck) {
    return <p className="p-6 text-sm text-danger-text">{apiErrorMessage(decksQuery.error)}</p>
  }

  return <Navigate to={ROUTES.vocabQuiz(deck.id)} replace />
}
