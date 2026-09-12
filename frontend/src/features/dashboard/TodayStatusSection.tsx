import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { ROUTES } from '../../constants/routes'
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
 * GET /records/today を別途呼ばない）。
 *
 * 報告ボタンは本日の状態によらず常に日次報告画面へ遷移させる（仕様書1.1（改20））。record_stateは
 * 未着手カテゴリを除外した集約値（仕様書7.2）のため、1カテゴリだけ確定した日も「報告済」に
 * なり、以前のように報告済を閲覧画面へ振ると残りのカテゴリを報告できなくなっていた。
 * 全カテゴリ確定済みの場合に閲覧画面へ転送する判定は、判定に必要な着手中の目標・書籍・案件を
 * 取得している日次報告画面（DailyReportPage）に一任する（DRYの原則、CODING_RULES.md「①DRYの原則」）。
 * 状態ラベルは表示用の集約値をそのまま用いる（6.1「本日の状態」）。 */
export function TodayStatusSection({ logicalDate, recordState }: TodayStatusSectionProps) {
  const statusKey = recordState ?? 'unreported'
  const dailyReportPath = ROUTES.dailyReport(logicalDate)

  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-600">
        {t('dashboard.todayStatus.label')}：{t(STATUS_LABEL_KEY[statusKey])}
      </span>
      <Link to={dailyReportPath}>
        <Button>{t('dashboard.reportButton.label')}</Button>
      </Link>
    </div>
  )
}
