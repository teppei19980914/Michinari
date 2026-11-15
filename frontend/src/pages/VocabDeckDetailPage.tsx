import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Button } from '../components/Button'
import { apiErrorMessage } from '../api/client'
import { getVocabDeck } from '../api/vocab'
import { VocabDeckHeader } from '../features/vocab/VocabDeckHeader'
import { VocabCardList } from '../features/vocab/VocabCardList'
import { VocabImportExportPanel } from '../features/vocab/VocabImportExportPanel'
import { QUERY_KEYS } from '../constants/queryKeys'

/** 単語帳詳細（開発Todo_単語帳_v1.0 要件A）。カードのCRUD・一括登録・書き出し・
 * 出題セッションへの入口をまとめる。 */
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

  const deck = deckQuery.data

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <Link to={ROUTES.goalDetail(deck.goal_id)} className="text-sm text-accent hover:underline">
        {t('vocab.deckDetail.backToGoal')}
      </Link>

      <VocabDeckHeader deck={deck} />

      <Link to={ROUTES.vocabQuiz(deck.id)}>
        <Button disabled={deck.card_count === 0}>{t('vocab.deckDetail.startQuizButton')}</Button>
      </Link>

      <VocabImportExportPanel deckId={deck.id} deckName={deck.name} />

      <VocabCardList deckId={deck.id} />
    </div>
  )
}
