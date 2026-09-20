import type { GoalCategory } from '../../api/goals'
import { resolveByGoalCategory } from './goalCategoryVariant'

/**
 * 目標一覧（SC-02）で種別を視覚的に区別するバッジの配色を判定する
 * （配布前改善S-08/S-10）。組み合わせが多く目視確認では漏れるためテスト対象とする。
 *
 * @param category 目標種別
 * @returns バッジに適用するTailwindクラス
 * @example resolveGoalCategoryBadgeClass('READING') // 'bg-emerald-100 text-emerald-800'
 */
export function resolveGoalCategoryBadgeClass(category: GoalCategory): string {
  return resolveByGoalCategory(category, {
    EXAM: 'bg-blue-100 text-blue-800',
    READING: 'bg-emerald-100 text-emerald-800',
    WORK: 'bg-amber-100 text-amber-800',
  })
}
