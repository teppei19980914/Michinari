import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { listGoals } from '../api/goals'
import { GoalTabBar } from '../features/record/GoalTabBar'
import { QualityTrendTab } from '../features/analytics/QualityTrendTab'
import { ProgressTab } from '../features/analytics/ProgressTab'
import { ForecastTab } from '../features/analytics/ForecastTab'
import { SpeedTrendTab } from '../features/analytics/SpeedTrendTab'
import { GanttTab } from '../features/analytics/GanttTab'
import { ReplanHistoryTab } from '../features/analytics/ReplanHistoryTab'
import { GrowthDescriptionTab } from '../features/analytics/GrowthDescriptionTab'
import { ReadingLogHistoryTab } from '../features/analytics/ReadingLogHistoryTab'
import { WorkLogHistoryTab } from '../features/analytics/WorkLogHistoryTab'
import { selectableAnalyticsGoals } from '../features/analytics/selectableAnalyticsGoals'

const EXAM_TABS = [
  { key: 'quality', labelKey: 'analytics.tabs.quality' },
  { key: 'progress', labelKey: 'analytics.tabs.progress' },
  { key: 'forecast', labelKey: 'analytics.tabs.forecast' },
  { key: 'speed', labelKey: 'analytics.tabs.speed' },
  { key: 'gantt', labelKey: 'analytics.tabs.gantt' },
  { key: 'replanHistory', labelKey: 'analytics.tabs.replanHistory' },
  { key: 'growthDescription', labelKey: 'analytics.tabs.growthDescription' },
] as const

/** 読書目標（category=READING）は品質推移等の5タブ+リプラン履歴がMaterial（教材）に
 * 依存し適用できないため、想起記録の一覧（読書記録）に置き換える（仕様書6.8補足）。 */
const READING_TABS = [
  { key: 'readingLog', labelKey: 'analytics.tabs.readingLog' },
  { key: 'growthDescription', labelKey: 'analytics.tabs.growthDescription' },
] as const

/** 仕事目標（category=WORK）も読書と同じ理由で業務記録の一覧に置き換える（仕様書6.8補足）。 */
const WORK_TABS = [
  { key: 'workLog', labelKey: 'analytics.tabs.workLog' },
  { key: 'growthDescription', labelKey: 'analytics.tabs.growthDescription' },
] as const

type TabKey =
  | (typeof EXAM_TABS)[number]['key']
  | (typeof READING_TABS)[number]['key']
  | (typeof WORK_TABS)[number]['key']

/** SC-09 分析（仕様書6.8）。目標を選択し、目標のカテゴリ（資格試験／読書／仕事）に応じた
 * タブ構成でデータを表示する。日次報告（DailyReportPage）と同じGoalTabBarで対象目標を
 * 切り替える方式に統一した（Phase25、分析タブの目標ごと表示の是正）。ダッシュボードの
 * 統計カードからは対象目標を指定した状態（?goal=<id>）で遷移してくる。目標タブに並べる
 * 対象（アーカイブ済み・下書きを除く）はselectableAnalyticsGoals.tsで判定する。
 * （features/dashboard/StatsSummary.tsx参照）。「成長記述」タブも選択中の目標宛てに
 * 絞り込む（Phase26で目標単位に分離、features/analytics/GrowthDescriptionTab.tsx参照）。 */
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

  const goals = selectableAnalyticsGoals(goalsQuery.data)
  const requestedGoalId = Number(searchParams.get('goal'))
  const selectedGoalId = goals.find((g) => g.id === requestedGoalId)?.id ?? goals[0]?.id
  const selectedGoal = goals.find((g) => g.id === selectedGoalId)
  const tabs =
    selectedGoal?.category === 'READING'
      ? READING_TABS
      : selectedGoal?.category === 'WORK'
        ? WORK_TABS
        : EXAM_TABS
  const activeTab: TabKey = tabs.some((item) => item.key === tab) ? tab : tabs[0].key

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('analytics.title')}</h1>

      {goals.length === 0 ? (
        <p className="text-sm text-gray-500">{t('analytics.goalSelector.empty')}</p>
      ) : (
        <>
          <GoalTabBar
            goals={goals}
            selectedGoalId={selectedGoalId ?? null}
            onSelect={(goalId) => setSearchParams({ goal: String(goalId) })}
          />

          <div className="flex flex-wrap gap-1 border-b border-gray-200">
            {tabs.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key)}
                className={`px-3 py-2 text-sm font-medium ${
                  activeTab === item.key
                    ? 'border-b-2 border-blue-600 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t(item.labelKey)}
              </button>
            ))}
          </div>

          {selectedGoalId !== undefined && selectedGoal?.category === 'EXAM' && (
            <>
              {activeTab === 'quality' && <QualityTrendTab goalId={selectedGoalId} />}
              {activeTab === 'progress' && <ProgressTab goalId={selectedGoalId} />}
              {activeTab === 'forecast' && <ForecastTab goalId={selectedGoalId} />}
              {activeTab === 'speed' && <SpeedTrendTab goalId={selectedGoalId} />}
              {activeTab === 'gantt' && <GanttTab goalId={selectedGoalId} />}
              {activeTab === 'replanHistory' && <ReplanHistoryTab goalId={selectedGoalId} />}
            </>
          )}
          {selectedGoalId !== undefined && selectedGoal?.category === 'READING' && (
            <>{activeTab === 'readingLog' && <ReadingLogHistoryTab goalId={selectedGoalId} />}</>
          )}
          {selectedGoalId !== undefined && selectedGoal?.category === 'WORK' && (
            <>{activeTab === 'workLog' && <WorkLogHistoryTab goalId={selectedGoalId} />}</>
          )}
        </>
      )}

      {activeTab === 'growthDescription' && selectedGoalId !== undefined && (
        <GrowthDescriptionTab goalId={selectedGoalId} goals={goals} />
      )}
    </div>
  )
}
