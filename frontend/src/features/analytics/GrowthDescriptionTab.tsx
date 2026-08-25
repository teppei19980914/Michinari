import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getGrowthDescriptions } from '../../api/analytics'

/** 分析画面「成長記述」タブ（仕様書6.8、ANL-07）。目標を横断してAI日次報告フィードバックの
 * 応答履歴を新しい日付順に表示する（データの紐付けについてはanalytics_service.
 * list_growth_descriptionsのdocstring、およびapi/analytics.pyのファイル冒頭コメントを参照）。
 * このタブのみ目標選択の影響を受けない。 */
export function GrowthDescriptionTab() {
  const query = useQuery({
    queryKey: ['analytics', 'growth-descriptions'],
    queryFn: getGrowthDescriptions,
  })

  if (query.isLoading) {
    return <p className="text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (query.isError || !query.data) {
    return <p className="text-sm text-red-600">{apiErrorMessage(query.error)}</p>
  }
  if (query.data.length === 0) {
    return <p className="text-sm text-gray-500">{t('analytics.growthDescription.empty')}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      {query.data.map((entry, index) => (
        <Card key={`${entry.record_date}-${index}`}>
          <p className="mb-1 text-xs text-gray-400">{entry.record_date}</p>
          <p className="whitespace-pre-wrap text-sm text-gray-900">{entry.content}</p>
        </Card>
      ))}
    </div>
  )
}
