/** ナレッジエクスポートのプレビュー/実行結果（KnowledgeExportContentRead.data）は
 * 出力項目選択によって含まれるキーが変わるため、バックエンドのスキーマでは
 * `Record<string, unknown>` として緩く型付けされている（backend/app/schemas/export.py）。
 * 画面表示に必要な最小限の形だけをここで定義する。
 */
export type QualityTrendPoint = { date: string; value: number }
export type QualityTrendEntry = { material: string; cycle: number; series: QualityTrendPoint[] }
export type ExportSummary = {
  total_minutes: number
  study_days: number
  report_rate: number
  replan_count: number
}

/**
 * 学習サマリの「最終到達品質」（仕様書6.10）を算出する。
 * データ構造編7.1のJSONスキーマにはこの値専用のフィールドが無いため、
 * quality_trend（周回別・粒度別の系列）の中で最も新しい日付の値を採用する
 * （複数教材・複数周回にまたがる場合、直近の実績が現在地を最もよく表すという解釈）。
 * 該当データが無い場合はnull（画面側は「算出不可」を表示する）。
 */
export function computeLatestQualityValue(entries: QualityTrendEntry[]): number | null {
  let latestDate: string | null = null
  let latestValue: number | null = null
  for (const entry of entries) {
    for (const point of entry.series) {
      if (latestDate === null || point.date > latestDate) {
        latestDate = point.date
        latestValue = point.value
      }
    }
  }
  return latestValue
}
