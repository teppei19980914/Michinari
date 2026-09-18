import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDashboard } from '../api/dashboard'
import { listGoals } from '../api/goals'
import { apiErrorMessage } from '../api/client'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { TodayMessage } from '../features/dashboard/TodayMessage'
import { WarningBanner } from '../features/dashboard/WarningBanner'
import { TodayStatusSection } from '../features/dashboard/TodayStatusSection'
import { TodayQuotaSection } from '../features/dashboard/TodayQuotaSection'
import { GoalCardList } from '../features/dashboard/GoalCardList'
import { StatsSummary } from '../features/dashboard/StatsSummary'
import { GoalTabBar } from '../features/record/GoalTabBar'
import { useGoalReportTabs } from '../features/record/useGoalReportTabs'
import { resolveTargetGoalId } from '../features/record/resolveTargetGoalId'
import { resolveDashboardGuard } from '../features/dashboard/resolveDashboardGuard'
import { QUERY_KEYS } from '../constants/queryKeys'

/** SC-01 ダッシュボード（仕様書6.1）。起動時の初期表示画面。
 *
 * GET /dashboard 1回でこの画面に必要な全情報（本日の状態を含む）を取得する
 * （データ構造編6.2「複数のリソースを個別に取得せず1回の呼び出しで返す」、
 * 初期表示2秒以内の性能要件）。今日の一言のみ例外として別クエリで非同期取得する。
 *
 * 進行中の目標が2件以上の場合、日次報告・カレンダーと同じGoalTabBarで対象目標を
 * 切り替える方式に統一した（Phase25、旧仕様6.1「全目標を1画面で俯瞰」の据え置き判断
 * （1.1改8）を撤回）。goal_cards・goal_stats・today_quota・warning・今日の一言は
 * いずれもgoal_id付きの配列としてAPIから返るため、バックエンド変更なしで
 * 選択中goal_idへの絞り込みのみで対応できる。本日の状態（record_state）・本日の
 * 日種別は目標に紐づかないアプリ全体の値のため、この目標切り替えの影響を受けない。 */
export function DashboardPage() {
  const location = useLocation()
  const dashboardQuery = useQuery({ queryKey: QUERY_KEYS.dashboard(), queryFn: getDashboard })
  const goalsQuery = useQuery({ queryKey: QUERY_KEYS.goals(), queryFn: () => listGoals() })
  const goalTabs = useGoalReportTabs(goalsQuery.data ?? [])
  const { reportableGoals, showGoalSelector, selectedGoalId, setSelectedGoalId } = goalTabs

  useEffect(() => {
    if (selectedGoalId === null && reportableGoals.length > 0) {
      setSelectedGoalId(reportableGoals[0].id)
    }
  }, [reportableGoals, selectedGoalId, setSelectedGoalId])

  // 表示状態（ローディング/エラー/表示可）の判定はresolveDashboardGuardへ集約している。
  // 全フックの呼び出しが済んだ後で評価する必要があるため、ここで呼ぶ。
  const guard = resolveDashboardGuard({ dashboard: dashboardQuery, goals: goalsQuery })
  if (guard.kind === 'LOADING') {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (guard.kind === 'ERROR') {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(guard.error)}</p>
  }

  // 目標が0件の初回起動時はウェルカム画面へ誘導する（仕様書「初回起動時のウェルカム画面」）。
  // 判定はDBの全goal件数（DRAFT等も含む）で都度行い、専用フラグは持たない。
  if ((goalsQuery.data ?? []).length === 0) {
    return <Navigate to={ROUTES.welcome} replace />
  }

  const dashboard = guard.dashboard
  const targetGoalId = resolveTargetGoalId(goalTabs)
  const goalCards = dashboard.goal_cards.filter((card) => card.goal_id === targetGoalId)
  const goalStats = dashboard.goal_stats.filter((stats) => stats.goal_id === targetGoalId)
  const todayQuota = dashboard.today_quota.filter((item) => item.goal_id === targetGoalId)
  const state = location.state as { showFirstRecordBanner?: boolean } | null
  const showFirstRecordBanner = state?.showFirstRecordBanner === true

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('dashboard.title')}</h1>

      {showFirstRecordBanner && (
        <p className="rounded-md bg-blue-50 p-3 text-sm text-blue-800">
          {t('dashboard.firstRecordBanner')}
        </p>
      )}

      {showGoalSelector && (
        <GoalTabBar
          goals={reportableGoals}
          selectedGoalId={selectedGoalId}
          onSelect={setSelectedGoalId}
        />
      )}

      <TodayMessage goalId={targetGoalId} />
      <WarningBanner goalCards={goalCards} />
      <TodayStatusSection logicalDate={dashboard.logical_date} recordState={dashboard.record_state} />
      <TodayQuotaSection
        todayQuota={todayQuota}
        availableSlotNames={dashboard.available_slot_names}
        isBufferDay={dashboard.today_day_type === 'BUFFER'}
      />
      <GoalCardList goalCards={goalCards} />
      <StatsSummary
        goalStats={goalStats}
        goalCards={goalCards}
        reportRateWindowDays={dashboard.report_rate_window_days}
      />
    </div>
  )
}
