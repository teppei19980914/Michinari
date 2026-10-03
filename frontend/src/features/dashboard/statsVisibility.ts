import type { GoalCategory } from '../../api/goals'
import type { DashboardRead } from '../../api/dashboard'

/** 目標カードから goal_id → カテゴリ の対応を作る。統計サマリ（GoalStatsRead）は
 * カテゴリを持たないため、同じ目標の目標カード（GoalCardRead）から引く。 */
export function buildCategoryByGoalId(
  goalCards: DashboardRead['goal_cards'],
): Record<number, GoalCategory> {
  return Object.fromEntries(goalCards.map((card) => [card.goal_id, card.category]))
}

/** 予備日消費率を表示するかを判定する。読書・仕事目標は日種別による計画運用の対象外で
 * （要件定義書R-71・R-74）、予備日（バッファ日）という概念自体を持たないため表示しない。
 * バックエンドも同じ理由でこれらのカテゴリには null を返す
 * （metrics_service.compute_buffer_usage_rate）。 */
export function showsBufferUsageRate(category: GoalCategory | undefined): boolean {
  return category === 'EXAM'
}
