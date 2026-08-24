import { useQuery } from '@tanstack/react-query'
import { getDashboard } from '../api/dashboard'
import { apiErrorMessage } from '../api/client'
import { t } from '../locales/t'
import { TodayMessage } from '../features/dashboard/TodayMessage'
import { WarningBanner } from '../features/dashboard/WarningBanner'
import { TodayStatusSection } from '../features/dashboard/TodayStatusSection'
import { TodayQuotaSection } from '../features/dashboard/TodayQuotaSection'
import { GoalCardList } from '../features/dashboard/GoalCardList'
import { StatsSummary } from '../features/dashboard/StatsSummary'

/** SC-01 ダッシュボード（仕様書6.1）。起動時の初期表示画面。
 *
 * GET /dashboard 1回でこの画面に必要な全情報（本日の状態を含む）を取得する
 * （データ構造編6.2「複数のリソースを個別に取得せず1回の呼び出しで返す」、
 * 初期表示2秒以内の性能要件）。今日の一言のみ例外として別クエリで非同期取得する。
 */
export function DashboardPage() {
  const dashboardQuery = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard })

  if (dashboardQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (dashboardQuery.isError || !dashboardQuery.data) {
    // 技術選定書7.3「エラーコードに対応するロケール文言を表示する」。
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(dashboardQuery.error)}</p>
  }

  const dashboard = dashboardQuery.data

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('dashboard.title')}</h1>
      <TodayMessage />
      <WarningBanner goalCards={dashboard.goal_cards} />
      <TodayStatusSection logicalDate={dashboard.logical_date} recordState={dashboard.record_state} />
      <TodayQuotaSection
        todayQuota={dashboard.today_quota}
        availableSlotNames={dashboard.available_slot_names}
        isBufferDay={dashboard.today_day_type === 'BUFFER'}
      />
      <GoalCardList goalCards={dashboard.goal_cards} />
      <StatsSummary goalStats={dashboard.goal_stats} reportRateWindowDays={dashboard.report_rate_window_days} />
    </div>
  )
}
