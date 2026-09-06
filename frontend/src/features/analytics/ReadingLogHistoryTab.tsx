import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getReadingLogAnalytics } from '../../api/analytics'

type ReadingLogHistoryTabProps = { goalId: number }

/** 分析画面「読書記録」タブ（読書目標category=READING向け、仕様書6.8補足）。
 * 資格試験の品質推移等5タブはMaterial（教材）に依存するため読書目標には適用できず、
 * 代わりに日々の想起記録を新しい順に列挙する（GET /analytics/reading-logs）。 */
export function ReadingLogHistoryTab({ goalId }: ReadingLogHistoryTabProps) {
  const query = useQuery({
    queryKey: ['analytics', 'reading-logs', goalId],
    queryFn: () => getReadingLogAnalytics(goalId),
  })

  if (query.isLoading) {
    return <p className="text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (query.isError || !query.data) {
    return <p className="text-sm text-red-600">{apiErrorMessage(query.error)}</p>
  }
  if (query.data.length === 0) {
    return <p className="text-sm text-gray-500">{t('analytics.readingLog.empty')}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      {query.data.map((entry, index) => (
        <Card key={`${entry.record_date}-${index}`}>
          <p className="mb-1 text-xs text-gray-400">{entry.record_date}</p>
          <p className="whitespace-pre-wrap text-sm text-gray-900">{entry.recall_body}</p>
          {entry.pages_read !== null && entry.current_page !== null && (
            <p className="mt-2 text-xs text-gray-500">
              {t('analytics.readingLog.pagesAndCurrentLabel', {
                pages: entry.pages_read,
                page: entry.current_page,
              })}
            </p>
          )}
          {entry.pages_read !== null && entry.current_page === null && (
            <p className="mt-2 text-xs text-gray-500">
              {t('analytics.readingLog.pagesReadLabel', { pages: entry.pages_read })}
            </p>
          )}
          {entry.pages_read === null && entry.current_page !== null && (
            <p className="mt-2 text-xs text-gray-500">
              {t('analytics.readingLog.currentPageLabel', { page: entry.current_page })}
            </p>
          )}
        </Card>
      ))}
    </div>
  )
}
