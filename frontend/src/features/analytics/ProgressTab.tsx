import { useQuery } from '@tanstack/react-query'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getProgressAnalytics } from '../../api/analytics'
import { GRID_LINE_COLOR, PLAN_LINE_COLOR, cycleSeriesColor } from './chartColors'
import { mergeProgressSeries } from './mergeProgressSeries'
import { formatAxisNumber, formatDateTick } from './formatPeriod'
import { QUERY_KEYS } from '../../constants/queryKeys'

type ProgressTabProps = { goalId: number }

/** 分析画面「進捗」タブ（仕様書6.8）。累積完了量（実績）と計画線を比較し、
 * 周回の区切りを縦の参照線で表示する。 */
export function ProgressTab({ goalId }: ProgressTabProps) {
  const query = useQuery({
    queryKey: QUERY_KEYS.analyticsProgress(goalId),
    queryFn: () => getProgressAnalytics(goalId),
  })

  return (
    <div className="flex flex-col gap-4">
      {query.isLoading && <p className="text-sm text-gray-500">{t('common.loading')}</p>}
      {query.isError && <p className="text-sm text-red-600">{apiErrorMessage(query.error)}</p>}

      {query.data && query.data.materials.length === 0 && (
        <p className="text-sm text-gray-500">{t('analytics.materialEmpty')}</p>
      )}

      {query.data?.materials.map((material) => {
        const rows = mergeProgressSeries(material.actual_points, material.plan_points)
        return (
          <Card key={material.material_id}>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-medium text-gray-900">{material.material_name}</h3>
              <span className="text-xs text-gray-500">
                {t('analytics.progress.unitTotalWork', {
                  total: material.total_work,
                  unit: material.unit_label,
                })}
              </span>
            </div>
            {rows.length === 0 ? (
              <p className="text-sm text-gray-500">{t('analytics.quality.noData')}</p>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={rows}>
                  <CartesianGrid stroke={GRID_LINE_COLOR} vertical={false} />
                  <XAxis dataKey="date" tickFormatter={formatDateTick} tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 'dataMax']} tick={{ fontSize: 12 }} tickFormatter={formatAxisNumber} />
                  <Tooltip labelFormatter={(value) => formatDateTick(String(value))} />
                  <Legend />
                  {material.cycle_boundaries.map((boundary) => (
                    <ReferenceLine
                      key={boundary.cycle_number}
                      x={boundary.record_date}
                      stroke={cycleSeriesColor(boundary.cycle_number - 1)}
                      strokeDasharray="4 4"
                      label={{
                        value: t('analytics.progress.cycleBoundaryLabel', {
                          cycle: boundary.cycle_number,
                        }),
                        position: 'top',
                        fontSize: 11,
                      }}
                    />
                  ))}
                  <Line
                    type="monotone"
                    dataKey="plan"
                    name={t('analytics.progress.planLegend')}
                    stroke={PLAN_LINE_COLOR}
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={false}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="actual"
                    name={t('analytics.progress.actualLegend')}
                    stroke={cycleSeriesColor(0)}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>
        )
      })}
    </div>
  )
}
