import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { apiErrorMessage } from '../api/client'
import { getVocabDeck } from '../api/vocab'
import { useToast } from '../components/toastContext'
import { VocabQuizSetupForm } from '../features/vocab/VocabQuizSetupForm'
import { VocabQuizQuestionView } from '../features/vocab/VocabQuizQuestionView'
import { VocabQuizSummaryView } from '../features/vocab/VocabQuizSummaryView'
import { useVocabQuizSession } from '../features/vocab/useVocabQuizSession'
import { MilestoneCelebrationModal } from '../features/milestone/MilestoneCelebrationModal'
import { QUERY_KEYS } from '../constants/queryKeys'

/** 単語帳の問題集・出題セッション（開発Todo_単語帳_v1.0 要件A）。AIは使わない。状態と
 * 操作はuseVocabQuizSessionへ切り出してある。セッションを終えたときの節目判定・お祝い
 * モーダル（要件E E-U3）も同フックが扱う。 */
export function VocabQuizPage() {
  const { deckId: deckIdParam } = useParams<{ deckId: string }>()
  const deckId = Number(deckIdParam)
  const { showApiError } = useToast()

  const deckQuery = useQuery({
    queryKey: QUERY_KEYS.vocabDeck(deckId),
    queryFn: () => getVocabDeck(deckId),
  })
  const session = useVocabQuizSession(deckId, deckQuery.data?.goal_id)

  if (deckQuery.isLoading) {
    return <p className="p-6 text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (deckQuery.isError || !deckQuery.data) {
    return <p className="p-6 text-sm text-danger-text">{apiErrorMessage(deckQuery.error)}</p>
  }
  const deck = deckQuery.data

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
      <Link to={ROUTES.vocabDeck(deckId)} className="text-sm text-accent hover:underline">
        {t('vocab.quiz.backToDeckButton')}
      </Link>
      <h1 className="text-xl font-semibold text-text-primary">{deck.name}</h1>

      {!session.mode && (
        <VocabQuizSetupForm
          termCardCount={deck.term_card_count}
          defaultQuestionCount={deck.session_default_questions}
          maxQuestionCount={deck.session_max_questions}
          onStart={session.start}
        />
      )}

      {session.mode && session.currentQuestion && (
        <>
          <p className="text-sm text-text-faint">
            {t('vocab.quiz.progressLabel', {
              current: session.index + 1,
              total: session.questions.length,
            })}
          </p>
          <VocabQuizQuestionView
            question={session.currentQuestion}
            lastResult={session.lastResult}
            onSubmit={session.answer}
            onNext={session.next}
          />
        </>
      )}

      {session.mode && session.questions.length > 0 && session.index >= session.questions.length && (
        <VocabQuizSummaryView
          deckId={deckId}
          summary={session.summary}
          isChecking={session.isChecking}
          onCheckWrongCards={() =>
            session.checkWrongCards(session.summary.wrongCards.map((c) => c.cardId))
          }
        />
      )}

      {session.mode && session.questions.length === 0 && (
        <p className="text-sm text-text-faint">{t('vocab.quiz.noQuestionsNotice')}</p>
      )}

      <MilestoneCelebrationModal
        milestone={session.milestone}
        onClose={() => session.dismissMilestone(showApiError)}
      />
    </div>
  )
}
