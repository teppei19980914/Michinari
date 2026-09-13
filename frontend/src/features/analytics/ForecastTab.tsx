import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getForecastAnalytics } from '../../api/analytics'
import { QUERY_KEYS } from '../../constants/queryKeys'

type ForecastTabProps = { goalId: number }

/** 分析画面「完了予測」タブ（仕様書6.8、ANL-05）。教材ごとの完了予測日と締切の乖離を表示する。 */
export function ForecastTab({ goalId }: ForecastTabProps) {
  const query = useQuery({
    queryKey: QUERY_KEYS.analyticsForecast(goalId),
    queryFn: () => getForecastAnalytics(goalId),
  })

  if (query.isLoading) {
    return <p className="text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (query.isError || !query.data) {
    return <p className="text-sm text-red-600">{apiErrorMessage(query.error)}</p>
  }

  if (query.data.materials.length === 0) {
    return <p className="text-sm text-gray-500">{t('analytics.materialEmpty')}</p>
  }

  return (
    <Card className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-gray-500">
            <th className="py-2 pr-4">{t('analytics.forecast.materialHeader')}</th>
            <th className="py-2 pr-4">{t('analytics.forecast.dueDateHeader')}</th>
            <th className="py-2 pr-4">{t('analytics.forecast.forecastDateHeader')}</th>
            <th className="py-2">{t('analytics.forecast.deviationHeader')}</th>
          </tr>
        </thead>
        <tbody>
          {query.data.materials.map((entry) => (
            <tr key={entry.material_id} className="border-b border-gray-100 text-gray-900">
              <td className="py-2 pr-4">{entry.material_name}</td>
              <td className="py-2 pr-4">{entry.due_date}</td>
              <td className="py-2 pr-4">
                {entry.forecast_date ??
                  (entry.unavailable_reason
                    ? t(`analytics.forecast.unavailable.${entry.unavailable_reason}`)
                    : '—')}
              </td>
              <td
                className={`py-2 ${
                  entry.overrun_days !== null && entry.overrun_days > 0
                    ? 'text-red-600'
                    : 'text-gray-900'
                }`}
              >
                {entry.overrun_days === null
                  ? '—'
                  : entry.overrun_days <= 0
                    ? t('analytics.forecast.onTrack')
                    : t('analytics.forecast.deviationDays', { days: entry.overrun_days })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
