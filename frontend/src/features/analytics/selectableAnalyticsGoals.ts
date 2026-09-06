import type { GoalRead } from '../../api/goals'

export type SelectableAnalyticsGoalsOptions = {
  /** アーカイブ済みの目標も対象に含めるか（分析画面のアーカイブ表示トグル、仕様書6.8） */
  includeArchived?: boolean
}

/**
 * 分析画面（SC-09）の目標タブに並べる目標を選ぶ（仕様書6.8）。
 *
 * 日次報告・カレンダー・ダッシュボード（useGoalReportTabs）が着手中（ACTIVE）に限定するのに対し、
 * 分析はクローズ済み目標の振り返りにも用いるためACTIVEには限定しない。ただし以下は除外する。
 *
 * - アーカイブ済み（archived_at !== null）：一覧から非表示にするための状態のため（要件定義書R-61）。
 *   目標一覧（SC-02）と同様に、利用者がトグルで表示を選んだ場合（includeArchived）のみ含める
 * - 下書き（DRAFT）：実績・記録が1件も存在せず、どのタブを開いても空になるため（トグルの対象外）
 */
export function selectableAnalyticsGoals(
  goals: GoalRead[],
  { includeArchived = false }: SelectableAnalyticsGoalsOptions = {},
): GoalRead[] {
  return goals.filter(
    (goal) => goal.status !== 'DRAFT' && (includeArchived || goal.archived_at === null),
  )
}

/**
 * アーカイブ表示トグルを出す価値がある（トグルをONにすると増える目標が存在する）かどうかを判定する。
 * 目標一覧（SC-02）と同じく、対象が0件のときはトグル自体を表示しない。
 */
export function hasArchivedAnalyticsGoals(goals: GoalRead[]): boolean {
  return selectableAnalyticsGoals(goals, { includeArchived: true }).some(
    (goal) => goal.archived_at !== null,
  )
}
