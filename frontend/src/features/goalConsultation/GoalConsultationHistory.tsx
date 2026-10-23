/** 目標相談チャットの相談履歴（一覧・削除、S10、開発Todo v1.1 V7）。
 *
 * 保存済みの質問・回答を一覧表示する。回答の表示は`GoalConsultationAnswerBody`を再利用する
 * （`GoalConsultationAnswerRead`と`GoalConsultationHistoryItemRead`はstatus/answer/
 * cited_dates/cited_weeksの形が同じため、CODING_RULES.md DRYの原則）。 */
import { apiErrorMessage } from '../../api/client'
import { dateTimeLocaleTag, t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import type { GoalConsultationHistoryItem } from '../../api/goalConsultation'
import { GoalConsultationAnswerBody } from './GoalConsultationAnswer'
import {
  useDeleteGoalConsultationHistoryItem,
  useGoalConsultationHistory,
} from './useGoalConsultation'

function HistoryItem({
  goalId,
  item,
}: {
  goalId: number
  item: GoalConsultationHistoryItem
}) {
  const { showApiError } = useToast()
  const deleteItem = useDeleteGoalConsultationHistoryItem(goalId)

  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs text-text-faint">{t('goalConsultation.historyQuestionLabel')}</p>
          <p className="text-sm text-text-primary whitespace-pre-wrap">{item.question}</p>
        </div>
        <Button
          variant="secondary"
          disabled={deleteItem.isPending}
          onClick={() => {
            if (window.confirm(t('common.confirmDelete'))) {
              deleteItem.mutate(item.id, { onError: showApiError })
            }
          }}
        >
          {t('common.action.delete')}
        </Button>
      </div>
      <GoalConsultationAnswerBody
        answer={{
          status: item.status,
          answer: item.answer,
          cited_dates: item.cited_dates,
          cited_weeks: item.cited_weeks,
        }}
      />
      <p className="text-xs text-text-disabled">
        {new Date(item.created_at).toLocaleString(dateTimeLocaleTag())}
      </p>
    </Card>
  )
}

export function GoalConsultationHistory({ goalId }: { goalId: number }) {
  const history = useGoalConsultationHistory(goalId)
  const items = history.data ?? []

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-text-primary">
        {t('goalConsultation.historyTitle')}
      </h3>
      {history.isLoading ? (
        <p className="text-sm text-text-faint">{t('common.loading')}</p>
      ) : history.isError ? (
        <p className="text-sm text-danger-text">{apiErrorMessage(history.error)}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-text-faint">{t('goalConsultation.historyEmpty')}</p>
      ) : (
        items.map((item) => <HistoryItem key={item.id} goalId={goalId} item={item} />)
      )}
    </div>
  )
}
