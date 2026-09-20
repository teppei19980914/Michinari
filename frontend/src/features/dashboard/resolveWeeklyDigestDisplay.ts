import type { DashboardRead } from '../../api/dashboard'

type WeeklyDigest = DashboardRead['weekly_digests'][number]

export type WeeklyDigestDisplay =
  | { kind: 'ai_summary'; text: string }
  | { kind: 'no_records' }
  | { kind: 'record_summary'; recordedDays: number; totalMinutes: number | null }

/** 先週のまとめ（仕様書6.1、S-4 4-4）の表示内容を判定する。
 *
 * AI週次要約（ai_summary_text）があればそれを優先し、無ければ非AI集計へフォールバック
 * する。記録日数が0件の場合は集計値ではなく「記録はありませんでした」の案内を出す
 * （0件・0分と表示しても利用者にとって意味のある情報にならないため）。 */
export function resolveWeeklyDigestDisplay(
  digest: Pick<WeeklyDigest, 'ai_summary_text' | 'recorded_days' | 'total_minutes'>,
): WeeklyDigestDisplay {
  if (digest.ai_summary_text !== null) {
    return { kind: 'ai_summary', text: digest.ai_summary_text }
  }
  if (digest.recorded_days === 0) {
    return { kind: 'no_records' }
  }
  return {
    kind: 'record_summary',
    recordedDays: digest.recorded_days,
    totalMinutes: digest.total_minutes,
  }
}
