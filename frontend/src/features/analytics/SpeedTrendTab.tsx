import { useQuery } from '@tanstack/react-query'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getSpeedAnalytics } from '../../api/analytics'
import { GRID_LINE_COLOR, cycleSeriesColor } from './chartColors'
import { cycleSeriesKey, mergeCycleSeries } from './mergeCycleSeries'
import { formatAxisNumber, formatDateTick } from './formatPeriod'
import { QUERY_KEYS } from '../../constants/queryKeys'

type SpeedTrendTabProps = { goalId: number }

/** 分析画面「実効速度」タブ（仕様書6.8、ANL-06）。単位時間あたり完了分量の推移を
 * 教材ごと・周回別に表示する。 */
export function SpeedTrendTab({ goalId }: SpeedTrendTabProps) {
  const query = useQuery({
    queryKey: QUERY_KEYS.analyticsSpeed(goalId),
    queryFn: () => getSpeedAnalytics(goalId),
  })

  return (
    <div className="flex flex-col gap-4">
      {query.isLoading && <p className="text-sm text-gray-500">{t('common.loading')}</p>}
      {query.isError && <p className="text-sm text-red-600">{apiErrorMessage(query.error)}</p>}

      {query.data && query.data.materials.length === 0 && (
        <p className="text-sm text-gray-500">{t('analytics.materialEmpty')}</p>
      )}

      {query.data?.materials.map((material) => {
        const { rows, cycleNumbers } = mergeCycleSeries(
          material.series.map((s) => ({
            cycleNumber: s.cycle_number,
            points: s.points.map((p) => ({ x: p.record_date, value: p.speed })),
          })),
        )
        return (
          <Card key={material.material_id}>
            <h3 className="mb-2 font-medium text-gray-900">{material.material_name}</h3>
            {rows.length === 0 ? (
              <p className="text-sm text-gray-500">{t('analytics.speed.noData')}</p>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={rows}>
                  <CartesianGrid stroke={GRID_LINE_COLOR} vertical={false} />
                  <XAxis dataKey="x" tickFormatter={formatDateTick} tick={{ fontSize: 12 }} />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickFormatter={formatAxisNumber}
                    label={{
                      value: `${material.unit_label}${t('analytics.speed.unitPerHour')}`,
                      angle: -90,
                      position: 'insideLeft',
                      fontSize: 11,
                    }}
                  />
                  <Tooltip labelFormatter={(value) => formatDateTick(String(value))} />
                  {cycleNumbers.length > 1 && <Legend />}
                  {cycleNumbers.map((cycleNumber, index) => (
                    <Line
                      key={cycleNumber}
                      type="monotone"
                      dataKey={cycleSeriesKey(cycleNumber)}
                      name={t('analytics.speed.cycleLegend', { cycle: cycleNumber })}
                      stroke={cycleSeriesColor(index)}
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>
        )
      })}
    </div>
  )
}
