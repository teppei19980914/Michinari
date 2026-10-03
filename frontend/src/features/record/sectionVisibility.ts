import type { GoalRead } from '../../api/goals'

export type GoalTabState = {
  /** 目標タブを表示しているか（着手中の目標が2件以上。useGoalReportTabs）。 */
  showGoalSelector: boolean
  /** タブで選択中の目標。タブ非表示のときはundefined。 */
  selectedGoal: GoalRead | undefined
}

/**
 * カテゴリ別セクションを表示するかを判定する（日次報告 SC-06・日次報告閲覧 SC-08 共通）。
 *
 * 目標タブが無い（着手中の目標が0〜1件）間は、選択状態に関わらず中身の有無だけで判定する。
 * タブがある場合は、そのタブが対象カテゴリを指しているときにだけ表示する。
 *
 * 両画面で同じ規則を使う必要がある。表示条件がずれると、同じ日の記録が入力画面と閲覧画面で
 * 違って見えるため、片方だけ直すのが最も危険な変更になる（CODING_RULES.md「①DRYの原則」）。
 *
 * @param tabs 目標タブの状態
 * @param category 判定対象のカテゴリ
 * @param hasContent そのカテゴリに表示すべき中身があるか（実績・日記・対話の有無）
 */
export function isSectionVisible(
  tabs: GoalTabState,
  category: GoalRead['category'],
  hasContent: boolean,
): boolean {
  if (!tabs.showGoalSelector) {
    return hasContent
  }
  return tabs.selectedGoal?.category === category && hasContent
}
