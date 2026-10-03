/** 比率(0〜1)を百分率表示へ整形する（CLAUDE.md DRYの原則。GoalCardList/StatsSummaryで共用）。
 * nullの場合の代替表示は呼び出し側がロケール文言で決める（項目ごとに文言が異なるため）。 */
export function formatPercent(rate: number): string {
  return `${Math.round(rate * 100)}%`
}
