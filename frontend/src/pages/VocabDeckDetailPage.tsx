import { Navigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { apiErrorMessage } from '../api/client'
import { getVocabDeck } from '../api/vocab'
import { QUERY_KEYS } from '../constants/queryKeys'

/** `/vocab/:deckId` の中継ページ（開発Todo_単語帳_出題導線改修_v1.0 D8）。単語帳
 * （デッキ）はユーザーに見せないため、デッキ自体の詳細画面は廃止し、そのデッキが属する
 * 目標の詳細画面（単語帳タブ）へ案内するだけにする。`QuizSession.tsx`の「単語帳で確認する」
 * リンク・`VocabQuizPage`/`VocabQuizSummaryView`の「戻る」リンクがこのルートを参照し続け
 * ているため、ルート自体（`ROUTES.vocabDeck`）は変更しない。 */
export function VocabDeckDetailPage() {
  const { deckId: deckIdParam } = useParams<{ deckId: string }>()
  const deckId = Number(deckIdParam)

  const deckQuery = useQuery({
    queryKey: QUERY_KEYS.vocabDeck(deckId),
    queryFn: () => getVocabDeck(deckId),
  })

  if (deckQuery.isLoading) {
    return <p className="p-6 text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (deckQuery.isError || !deckQuery.data) {
    return <p className="p-6 text-sm text-danger-text">{apiErrorMessage(deckQuery.error)}</p>
  }

  return <Navigate to={ROUTES.goalDetail(deckQuery.data.goal_id)} replace />
}
