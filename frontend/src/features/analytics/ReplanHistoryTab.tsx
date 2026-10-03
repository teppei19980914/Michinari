import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getBaselines, getGoal } from '../../api/goals'
import { buildReplanHistoryRows } from './replanHistoryRows'
import { QUERY_KEYS } from '../../constants/queryKeys'

type ReplanHistoryTabProps = { goalId: number }

/** 分析画面「リプラン履歴」タブ（仕様書6.8、ANL-08）。Phase3で実装済みの
 * GET /goals/{id}/baselines をそのまま再利用する（新規エンドポイントを追加しない）。 */
export function ReplanHistoryTab({ goalId }: ReplanHistoryTabProps) {
  const goalQuery = useQuery({ queryKey: QUERY_KEYS.goal(goalId), queryFn: () => getGoal(goalId) })
  const baselinesQuery = useQuery({
    queryKey: QUERY_KEYS.analyticsBaselines(goalId),
    queryFn: () => getBaselines(goalId),
  })

  if (goalQuery.isLoading || baselinesQuery.isLoading) {
    return <p className="text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (goalQuery.isError || !goalQuery.data) {
    return <p className="text-sm text-red-600">{apiErrorMessage(goalQuery.error)}</p>
  }
  if (baselinesQuery.isError || !baselinesQuery.data) {
    return <p className="text-sm text-red-600">{apiErrorMessage(baselinesQuery.error)}</p>
  }

  const materialNameById = new Map(goalQuery.data.materials.map((m) => [m.id, m.name]))
  const rows = buildReplanHistoryRows(baselinesQuery.data, materialNameById)

  if (rows.length === 0) {
    return <p className="text-sm text-gray-500">{t('analytics.replanHistory.empty')}</p>
  }

  return (
    <Card className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-gray-500">
            <th className="py-2 pr-4">{t('analytics.replanHistory.dateHeader')}</th>
            <th className="py-2 pr-4">{t('analytics.replanHistory.materialHeader')}</th>
            <th className="py-2 pr-4">{t('analytics.replanHistory.reasonHeader')}</th>
            <th className="py-2 pr-4">{t('analytics.replanHistory.quotaBeforeHeader')}</th>
            <th className="py-2">{t('analytics.replanHistory.quotaAfterHeader')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-gray-100 text-gray-900">
              <td className="py-2 pr-4">{row.effectiveFrom}</td>
              <td className="py-2 pr-4">{row.materialName}</td>
              <td className="py-2 pr-4">{t(`analytics.replanHistory.reason.${row.reason}`)}</td>
              <td className="py-2 pr-4">
                {row.quotaBefore === null ? '—' : row.quotaBefore.toFixed(2)}
              </td>
              <td className="py-2">{row.quotaAfter.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
