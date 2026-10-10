/** 読み込んだ報告が「どの対象期間の、どの報告月の報告か」を示す見出し（WorkReportTab.tsx）。
 *
 * 表示名（"2026年9月"・"2026年3月〜8月"）は、サーバが報告から組み立てた値を使う。入力欄の値は
 * 取得条件であり、空欄なら前期分が出るため、入力欄の値を表示すると実際の報告と食い違う。
 * 報告月は月次報告のみ値を持つ。値が無い（半期評価）場合は対象半期だけを表示する。 */
import { t } from '../../locales/t'

export function WorkReportPeriodHeader({
  targetLabel,
  reportingLabel,
}: {
  targetLabel: string
  reportingLabel: string | null
}) {
  return (
    <p className="text-sm font-medium text-text-primary">
      {reportingLabel
        ? t('goals.workReport.periodHeaderMonthly', { target: targetLabel, reporting: reportingLabel })
        : t('goals.workReport.periodHeaderSemiannual', { target: targetLabel })}
    </p>
  )
}
