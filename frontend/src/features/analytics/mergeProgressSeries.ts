/**
 * 進捗タブ: 実績の累積完了量と計画線をRechartsの1データセットへ結合する
 * （actual_points・plan_pointsはAPIでは別配列だが、Rechartsは同一行に両キーがある
 * 形を要求するため、日付をキーに突合する）。
 */

export type ProgressPointInput = { record_date: string; cumulative_completed: number }
export type MergedProgressRow = { date: string; actual?: number; plan?: number }

export function mergeProgressSeries(
  actualPoints: ProgressPointInput[],
  planPoints: ProgressPointInput[],
): MergedProgressRow[] {
  const rowByDate = new Map<string, MergedProgressRow>()

  for (const p of actualPoints) {
    const row = rowByDate.get(p.record_date) ?? { date: p.record_date }
    row.actual = p.cumulative_completed
    rowByDate.set(p.record_date, row)
  }
  for (const p of planPoints) {
    const row = rowByDate.get(p.record_date) ?? { date: p.record_date }
    row.plan = p.cumulative_completed
    rowByDate.set(p.record_date, row)
  }

  return [...rowByDate.values()].sort((a, b) => a.date.localeCompare(b.date))
}
