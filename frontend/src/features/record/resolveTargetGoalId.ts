import type { GoalReportTabs } from './useGoalReportTabs'

/** GoalTabBarで対象目標を切り替える画面（カレンダー・ダッシュボード・日次報告）共通の、
 * 「現在どの目標のデータを表示すべきか」を1つのgoal_idに解決する処理（CLAUDE.md DRYの原則）。
 *
 * useGoalReportTabs.selectedGoalは着手中の目標が2件以上のとき（showGoalSelector=true）
 * のみ値を持つ設計のため、0〜1件のケースをこの関数で補う。着手中の目標が0件のときは
 * nullを返し、呼び出し側は目標非依存の表示（または非表示）にフォールバックする。 */
export function resolveTargetGoalId(tabs: GoalReportTabs): number | null {
  if (tabs.selectedGoal) {
    return tabs.selectedGoal.id
  }
  if (!tabs.showGoalSelector && tabs.reportableGoals.length === 1) {
    return tabs.reportableGoals[0].id
  }
  return null
}
