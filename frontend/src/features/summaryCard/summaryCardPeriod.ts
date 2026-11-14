export type SummaryCardPeriod = { dateFrom: string; dateTo: string }

/** SC-03 期間指定モードの既定期間：当年1/1〜サーバの論理日（仕様書6.2、R-154〜R-159）。
 * クライアント側で論理日を判断しない既存ルール（CLAUDE.md）に従い、`logicalDate`は
 * `GET /records/today`から渡される前提とする。 */
export function defaultOpenPeriod(logicalDate: string): SummaryCardPeriod {
  const year = logicalDate.slice(0, 4)
  return { dateFrom: `${year}-01-01`, dateTo: logicalDate }
}

/** SC-13 目標完了時モードの固定期間：目標の開始日〜クローズ日（変更不可、仕様書6.10）。
 * `closedAt`はISO日時文字列（例: "2026-11-13T09:00:00+00:00"）のため日付部分のみ使う。 */
export function closedGoalPeriod(startDate: string, closedAt: string): SummaryCardPeriod {
  return { dateFrom: startDate, dateTo: closedAt.slice(0, 10) }
}
