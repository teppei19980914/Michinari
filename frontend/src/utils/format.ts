/** 比率(0〜1)を百分率表示へ整形する（CLAUDE.md DRYの原則。GoalCardList/StatsSummaryで共用）。
 * nullの場合の代替表示は呼び出し側がロケール文言で決める（項目ごとに文言が異なるため）。 */
export function formatPercent(rate: number): string {
  return `${Math.round(rate * 100)}%`
}

/** 暦月のperiod_key（"YYYY-MM"）を "YYYY年M月" へ整形する（月次報告の対象月・報告月の表示用）。
 * 想定外の形式は加工せずそのまま返す（表示を壊さないため）。 */
export function formatMonthKey(periodKey: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(periodKey)
  if (!match) {
    return periodKey
  }
  return `${Number(match[1])}年${Number(match[2])}月`
}
