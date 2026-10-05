/** 読み込んだ月次報告が「どの対象月の、どの報告月の報告か」を示す見出し（WorkReportTab.tsx）。
 *
 * 表示する値は、入力欄の内容ではなく読み込んだ報告（サーバ応答）の期間を使う。入力欄は取得条件で
 * あり、空欄なら前月分が出るため、入力欄の値を表示すると実際の報告と食い違うためである。 */
import { t } from '../../locales/t'
import { formatMonthKey } from '../../utils/format'

export function WorkReportPeriodHeader({
  periodKey,
  reportingPeriodKey,
}: {
  periodKey: string
  reportingPeriodKey: string
}) {
  return (
    <p className="text-sm font-medium text-gray-800">
      {t('goals.workReport.periodHeader', {
        target: formatMonthKey(periodKey),
        reporting: formatMonthKey(reportingPeriodKey),
      })}
    </p>
  )
}
