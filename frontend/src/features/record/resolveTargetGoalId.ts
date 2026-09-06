import type { GoalReportTabs } from './useGoalReportTabs'

/** GoalTabBarで対象目標を切り替える画面のうち、カレンダー・ダッシュボードで共通の、
 * 「現在どの目標のデータを表示すべきか」を1つのgoal_idに解決する処理（CLAUDE.md DRYの原則）。
 * 日次報告（DailyReportPage/DailyReportViewPage）は対象外：あちらは「カテゴリ別に入力欄
 * を出し分ける」という別形状の分岐（goal_id単位ではなくEXAM/READING/WORKごとの表示要否）
 * のため、この関数の対象にしていない。
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
