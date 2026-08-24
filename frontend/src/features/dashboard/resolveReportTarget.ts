import { ROUTES } from '../../constants/routes'
import type { components } from '../../types/api.d.ts'

type RecordState = components['schemas']['RecordState']

/**
 * 本日の状態に応じた「本日の報告ボタン」の遷移先を判定する（仕様書6.1「本日の状態に応じて
 * 遷移先を切り替える」、7.2「日付の記録状態遷移」）。
 *
 * 未入力・進捗のみ登録済の場合は日次報告（SC-06、進捗のみ登録済からは昇格）へ、
 * 報告済の場合は確定済みで変更不可のため日次報告閲覧（SC-08）へ遷移する。
 */
export function resolveReportTarget(recordState: RecordState | null, logicalDate: string): string {
  if (recordState === 'REPORTED') {
    return ROUTES.dailyReportView(logicalDate)
  }
  return ROUTES.dailyReport(logicalDate)
}
