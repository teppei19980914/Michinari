import type { GoalRead } from '../../api/goals'

/**
 * 分析画面（SC-09）の目標タブに並べる目標を選ぶ（仕様書6.8）。
 *
 * 日次報告・カレンダー・ダッシュボード（useGoalReportTabs）が着手中（ACTIVE）に限定するのに対し、
 * 分析はクローズ済み目標の振り返りにも用いるためACTIVEには限定しない。ただし以下は除外する。
 *
 * - アーカイブ済み（archived_at !== null）：一覧から非表示にするための状態のため（要件定義書R-61）
 * - 下書き（DRAFT）：実績・記録が1件も存在せず、どのタブを開いても空になるため
 */
export function selectableAnalyticsGoals(goals: GoalRead[]): GoalRead[] {
  return goals.filter((goal) => goal.archived_at === null && goal.status !== 'DRAFT')
}
