import type { GoalCategory } from '../../api/goals'
import type { GoalReportTabs } from './useGoalReportTabs'

/** DailyReportPageで、カテゴリ（資格試験／読書／仕事）ごとのAI対話対象goal_idを解決する
 * （Phase26レビューで発見したDRY違反の是正。examGoalId/readingGoalId/workGoalIdの3箇所で
 * 同型の三項演算子が重複していたため集約した）。
 *
 * 目標タブ表示中（showGoalSelector=true）は、選択中の目標が指定カテゴリと一致する場合のみ
 * その目標を返す（他カテゴリのタブを見ている間はnull）。タブ非表示（着手中の目標が0〜1件）
 * のときは、呼び出し側があらかじめ解決した1件分のfallbackGoalId（該当カテゴリの目標が
 * 存在すればそのid、なければnull）をそのまま返す。 */
export function resolveCategoryGoalId(
  tabs: Pick<GoalReportTabs, 'showGoalSelector' | 'selectedGoal'>,
  category: GoalCategory,
  fallbackGoalId: number | null,
): number | null {
  if (tabs.showGoalSelector) {
    return tabs.selectedGoal && tabs.selectedGoal.category === category
      ? tabs.selectedGoal.id
      : null
  }
  return fallbackGoalId
}
