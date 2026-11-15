import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import type { VocabSessionSummary } from './vocabQuizProgress'

/** 出題セッションの結果表示。間違えた用語にまとめてチェックを付けられる。 */
export function VocabQuizSummaryView({
  deckId,
  summary,
  onCheckWrongCards,
  isChecking,
}: {
  deckId: number
  summary: VocabSessionSummary
  onCheckWrongCards: () => void
  isChecking: boolean
}) {
  return (
    <Card className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold text-text-primary">
        {t('vocab.quiz.completedTitle')}
      </h2>
      <p className="text-sm text-text-secondary">
        {t('vocab.quiz.scoreLabel', {
          correct: summary.correctCount,
          total: summary.totalCount,
        })}
      </p>

      {summary.wrongCards.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-text-primary">
            {t('vocab.quiz.wrongTermsTitle')}
          </h3>
          <ul className="flex flex-col gap-1 text-sm text-text-secondary">
            {summary.wrongCards.map((card) => <li key={card.cardId}>{card.term}</li>)}
          </ul>
          <Button disabled={isChecking} onClick={onCheckWrongCards}>
            {t('vocab.quiz.checkWrongButton')}
          </Button>
        </div>
      )}

      <Link to={ROUTES.vocabDeck(deckId)} className="text-sm text-accent hover:underline">
        {t('vocab.quiz.backToDeckButton')}
      </Link>
    </Card>
  )
}
