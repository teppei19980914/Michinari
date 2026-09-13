/** 月次報告・半期評価（WorkReportTab.tsx）の種別ごとの差分を1箇所へ集約する。
 *
 * 取得・生成・保存の3種のAPIと、期間欄のラベル・書式例が種別で入れ替わる。呼び分けを
 * 取り違えると、月次報告の画面で半期評価を読み書きしてしまい、画面上は同じ形のため
 * 気づきにくい。判定をこの純粋関数に集めて単体テストで固定する（OPERATIONS.md
 * 「フロントエンドのテストとカバレッジ」）。 */
import {
  generateMonthlyReport,
  generateSemiannualReview,
  getMonthlyReport,
  getSemiannualReview,
  updateMonthlyReport,
  updateSemiannualReview,
} from '../../api/closure'
import type { WorkReportKind } from '../../constants/queryKeys'

export interface WorkReportKindConfig {
  getReport: typeof getMonthlyReport
  generateReport: typeof generateMonthlyReport
  updateReport: typeof updateMonthlyReport
  /** 期間欄のラベル（ロケールキー）。 */
  periodLabelKey: string
  /** 期間欄の書式例。入力形式が種別で異なるため、プレースホルダで示す。 */
  periodPlaceholder: string
  /** 翌期の目標欄のラベル（ロケールキー）。 */
  nextGoalTextLabelKey: string
  /** 特記事項欄を出すか。半期評価は持たない項目のため、入力欄も送信内容からも外す。 */
  showReportNotes: boolean
}

export function resolveWorkReportKind(kind: WorkReportKind): WorkReportKindConfig {
  if (kind === 'monthly') {
    return {
      getReport: getMonthlyReport,
      generateReport: generateMonthlyReport,
      updateReport: updateMonthlyReport,
      periodLabelKey: 'goals.workReport.periodLabelMonthly',
      periodPlaceholder: 'YYYY-MM',
      nextGoalTextLabelKey: 'goals.workReport.nextGoalTextLabelMonthly',
      showReportNotes: true,
    }
  }
  return {
    getReport: getSemiannualReview,
    generateReport: generateSemiannualReview,
    updateReport: updateSemiannualReview,
    periodLabelKey: 'goals.workReport.periodLabelSemiannual',
    periodPlaceholder: 'YYYY-H1 / YYYY-H2',
    nextGoalTextLabelKey: 'goals.workReport.nextGoalTextLabelSemiannual',
    showReportNotes: false,
  }
}
