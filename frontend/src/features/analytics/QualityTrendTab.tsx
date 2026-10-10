import { useState } from 'react'
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
import { getQualityAnalytics, type Granularity } from '../../api/analytics'
import { cycleSeriesColor, resolveGridLineColor, THRESHOLD_LINE_COLOR } from './chartColors'
import { cycleSeriesKey, mergeCycleSeries } from './mergeCycleSeries'
import { formatAxisNumber, formatPeriodLabel } from './formatPeriod'
import { QUERY_KEYS } from '../../constants/queryKeys'

const GRANULARITIES: Granularity[] = ['DAY', 'WEEK', 'MONTH']

type QualityTrendTabProps = { goalId: number }

/** 分析画面「品質推移」タブ（仕様書6.8、ANL-01〜03）。粒度切替・合格基準線・
 * 周回別系列分離を教材ごとに表示する。 */
export function QualityTrendTab({ goalId }: QualityTrendTabProps) {
  const [granularity, setGranularity] = useState<Granularity>('WEEK')
  const query = useQuery({
    queryKey: QUERY_KEYS.analyticsQuality(goalId, granularity),
    queryFn: () => getQualityAnalytics(goalId, granularity),
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <span className="text-sm text-text-muted">{t('analytics.quality.granularityLabel')}</span>
        <div className="flex gap-1">
          {GRANULARITIES.map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => setGranularity(g)}
              className={`rounded px-2 py-1 text-sm ${
                granularity === g ? 'bg-accent text-white' : 'bg-surface-muted text-text-secondary'
              }`}
            >
              {t(`settings.display.granularity.${g}`)}
            </button>
          ))}
        </div>
      </div>

      {query.isLoading && <p className="text-sm text-text-faint">{t('common.loading')}</p>}
      {query.isError && <p className="text-sm text-danger-text">{apiErrorMessage(query.error)}</p>}

      {query.data && query.data.materials.length === 0 && (
        <p className="text-sm text-text-faint">{t('analytics.materialEmpty')}</p>
      )}

      {query.data?.materials.map((material) => {
        const { rows, cycleNumbers } = mergeCycleSeries(
          material.series.map((s) => ({
            cycleNumber: s.cycle_number,
            points: s.points.map((p) => ({ x: p.period_start, value: p.value })),
          })),
        )
        return (
          <Card key={material.material_id}>
            <h3 className="mb-2 font-medium text-text-primary">{material.material_name}</h3>
            {rows.length === 0 ? (
              <p className="text-sm text-text-faint">{t('analytics.quality.noData')}</p>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={rows}>
                  <CartesianGrid stroke={resolveGridLineColor()} vertical={false} />
                  <XAxis
                    dataKey="x"
                    tickFormatter={(value: string) => formatPeriodLabel(value, granularity)}
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} tickFormatter={formatAxisNumber} />
                  <Tooltip
                    labelFormatter={(value) => formatPeriodLabel(String(value), granularity)}
                  />
                  {cycleNumbers.length > 1 && <Legend />}
                  {material.passing_score !== null && (
                    <ReferenceLine
                      y={material.passing_score}
                      stroke={THRESHOLD_LINE_COLOR}
                      strokeDasharray="4 4"
                      label={{
                        value: t('analytics.quality.passingScoreLegend'),
                        position: 'insideTopRight',
                        fontSize: 12,
                      }}
                    />
                  )}
                  {cycleNumbers.map((cycleNumber, index) => (
                    <Line
                      key={cycleNumber}
                      type="monotone"
                      dataKey={cycleSeriesKey(cycleNumber)}
                      name={t('analytics.quality.cycleLegend', { cycle: cycleNumber })}
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
