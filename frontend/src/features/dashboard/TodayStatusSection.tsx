import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { resolveReportTarget } from './resolveReportTarget'
import type { DashboardRead } from '../../api/dashboard'

const STATUS_LABEL_KEY: Record<'unreported' | 'PROGRESS_ONLY' | 'REPORTED', string> = {
  unreported: 'dashboard.todayStatus.unreported',
  PROGRESS_ONLY: 'dashboard.todayStatus.progressOnly',
  REPORTED: 'dashboard.todayStatus.reported',
}

type TodayStatusSectionProps = {
  logicalDate: DashboardRead['logical_date']
  recordState: DashboardRead['record_state']
}

/** 本日の状態表示と「本日の報告ボタン」（仕様書6.1）。
 * logical_date/record_state は GET /dashboard のレスポンスから取得する
 * （データ構造編6.2「複数のリソースを個別に取得せず1回の呼び出しで返す」ため、
 * GET /records/today を別途呼ばない）。 */
export function TodayStatusSection({ logicalDate, recordState }: TodayStatusSectionProps) {
  const statusKey = recordState ?? 'unreported'
  const target = resolveReportTarget(recordState, logicalDate)

  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-600">
        {t('dashboard.todayStatus.label')}：{t(STATUS_LABEL_KEY[statusKey])}
      </span>
      <Link to={target}>
        <Button>{t('dashboard.reportButton.label')}</Button>
      </Link>
    </div>
  )
}
