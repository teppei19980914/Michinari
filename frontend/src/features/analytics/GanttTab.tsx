import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getGanttAnalytics } from '../../api/analytics'
import { computeGanttLayout } from './ganttGeometry'
import { QUERY_KEYS } from '../../constants/queryKeys'

type GanttTabProps = { goalId: number }

/** 分析画面「ガントチャート」タブ（仕様書6.8、ANL-04）。技術選定書の方針通り、
 * 専用ライブラリを使わずCSS Grid + Tailwindで自作する。 */
export function GanttTab({ goalId }: GanttTabProps) {
  const query = useQuery({
    queryKey: QUERY_KEYS.analyticsGantt(goalId),
    queryFn: () => getGanttAnalytics(goalId),
  })

  if (query.isLoading) {
    return <p className="text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (query.isError || !query.data) {
    return <p className="text-sm text-red-600">{apiErrorMessage(query.error)}</p>
  }

  const { materials, today } = query.data
  if (materials.length === 0) {
    return <p className="text-sm text-gray-500">{t('analytics.gantt.empty')}</p>
  }

  const { entries, todayPercent } = computeGanttLayout(materials, today)
  const entryByMaterialId = new Map(entries.map((e) => [e.material_id, e]))

  return (
    <Card>
      <div className="relative flex flex-col gap-3">
        {todayPercent !== null && (
          <div
            className="pointer-events-none absolute top-0 bottom-0 w-px bg-red-500"
            style={{ left: `${todayPercent}%` }}
            title={t('analytics.gantt.todayLabel')}
          />
        )}
        {materials.map((material) => {
          const layout = entryByMaterialId.get(material.material_id)
          if (!layout) {
            return null
          }
          return (
            <div key={material.material_id} className="flex flex-col gap-1">
              <div className="flex items-center justify-between text-xs text-gray-600">
                <span>{material.material_name}</span>
                <span>
                  {material.start_date} 〜 {material.due_date}
                </span>
              </div>
              <div className="relative h-4 w-full rounded bg-gray-100">
                <div
                  className="absolute top-0 h-full rounded bg-blue-200"
                  style={{ left: `${layout.leftPercent}%`, width: `${layout.widthPercent}%` }}
                >
                  <div
                    className="h-full rounded bg-blue-500"
                    style={{
                      width:
                        layout.widthPercent > 0
                          ? `${(layout.progressWidthPercent / layout.widthPercent) * 100}%`
                          : '0%',
                    }}
                  />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
