import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { listGoals } from '../api/goals'
import { QualityTrendTab } from '../features/analytics/QualityTrendTab'
import { ProgressTab } from '../features/analytics/ProgressTab'
import { ForecastTab } from '../features/analytics/ForecastTab'
import { SpeedTrendTab } from '../features/analytics/SpeedTrendTab'
import { GanttTab } from '../features/analytics/GanttTab'
import { ReplanHistoryTab } from '../features/analytics/ReplanHistoryTab'
import { GrowthDescriptionTab } from '../features/analytics/GrowthDescriptionTab'

const TABS = [
  { key: 'quality', labelKey: 'analytics.tabs.quality' },
  { key: 'progress', labelKey: 'analytics.tabs.progress' },
  { key: 'forecast', labelKey: 'analytics.tabs.forecast' },
  { key: 'speed', labelKey: 'analytics.tabs.speed' },
  { key: 'gantt', labelKey: 'analytics.tabs.gantt' },
  { key: 'replanHistory', labelKey: 'analytics.tabs.replanHistory' },
  { key: 'growthDescription', labelKey: 'analytics.tabs.growthDescription' },
] as const

type TabKey = (typeof TABS)[number]['key']

/** SC-09 分析（仕様書6.8、7タブ構成）。目標を選択し、教材別の各種推移・ガント・
 * リプラン履歴・成長記述を表示する。ダッシュボードの統計カードからは対象目標を
 * 指定した状態（?goal=<id>）で遷移してくる（features/dashboard/StatsSummary.tsx参照）。
 * 「成長記述」タブのみ目標を横断したデータのため目標選択の影響を受けない
 * （features/analytics/GrowthDescriptionTab.tsx参照）。 */
export function AnalyticsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [tab, setTab] = useState<TabKey>('quality')

  const goalsQuery = useQuery({ queryKey: ['goals'], queryFn: listGoals })

  if (goalsQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (goalsQuery.isError || !goalsQuery.data) {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(goalsQuery.error)}</p>
  }

  const goals = goalsQuery.data
  const requestedGoalId = Number(searchParams.get('goal'))
  const selectedGoalId =
    goals.find((g) => g.id === requestedGoalId)?.id ?? goals[0]?.id

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('analytics.title')}</h1>

      {goals.length === 0 ? (
        <p className="text-sm text-gray-500">{t('analytics.goalSelector.empty')}</p>
      ) : (
        <>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            {t('analytics.goalSelector.label')}
            <select
              className="rounded border border-gray-300 px-2 py-1"
              value={String(selectedGoalId)}
              onChange={(event) => setSearchParams({ goal: event.target.value })}
            >
              {goals.map((goal) => (
                <option key={goal.id} value={goal.id}>
                  {goal.name}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-wrap gap-1 border-b border-gray-200">
            {TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key)}
                className={`px-3 py-2 text-sm font-medium ${
                  tab === item.key
                    ? 'border-b-2 border-blue-600 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t(item.labelKey)}
              </button>
            ))}
          </div>

          {selectedGoalId !== undefined && (
            <>
              {tab === 'quality' && <QualityTrendTab goalId={selectedGoalId} />}
              {tab === 'progress' && <ProgressTab goalId={selectedGoalId} />}
              {tab === 'forecast' && <ForecastTab goalId={selectedGoalId} />}
              {tab === 'speed' && <SpeedTrendTab goalId={selectedGoalId} />}
              {tab === 'gantt' && <GanttTab goalId={selectedGoalId} />}
              {tab === 'replanHistory' && <ReplanHistoryTab goalId={selectedGoalId} />}
            </>
          )}
        </>
      )}

      {tab === 'growthDescription' && <GrowthDescriptionTab />}
    </div>
  )
}
