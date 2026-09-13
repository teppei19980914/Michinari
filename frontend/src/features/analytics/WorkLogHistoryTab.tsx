import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getWorkLogAnalytics } from '../../api/analytics'
import { QUERY_KEYS } from '../../constants/queryKeys'

type WorkLogHistoryTabProps = { goalId: number }

/** 分析画面「業務記録」タブ（仕事目標category=WORK向け、仕様書6.8補足）。
 * 読書と同じ理由でMaterial非依存の一覧表示とし、日々の業務記録を新しい順に
 * 列挙する（GET /analytics/work-logs）。 */
export function WorkLogHistoryTab({ goalId }: WorkLogHistoryTabProps) {
  const query = useQuery({
    queryKey: QUERY_KEYS.analyticsWorkLogs(goalId),
    queryFn: () => getWorkLogAnalytics(goalId),
  })

  if (query.isLoading) {
    return <p className="text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (query.isError || !query.data) {
    return <p className="text-sm text-red-600">{apiErrorMessage(query.error)}</p>
  }
  if (query.data.length === 0) {
    return <p className="text-sm text-gray-500">{t('analytics.workLog.empty')}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      {query.data.map((entry, index) => (
        <Card key={`${entry.record_date}-${index}`}>
          <p className="mb-1 text-xs text-gray-400">{entry.record_date}</p>
          <p className="whitespace-pre-wrap text-sm text-gray-900">{entry.body}</p>
        </Card>
      ))}
    </div>
  )
}
