/** 未入力の前日を選んだときに出す「日次報告 / 進捗のみ登録」の選択モーダル（仕様書6.4）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた CalendarPage から
 * 切り出したものである。どちらを選んだかで進む先が変わるだけで、選択の判定そのものは
 * resolveCalendarDateAction.ts が担う。 */
import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { ROUTES } from '../../constants/routes'

export function ReportTypeChoiceModal({
  targetDate,
  onClose,
}: {
  /** 選択対象の日。閉じている間は null。 */
  targetDate: string | null
  onClose: () => void
}) {
  return (
    <Modal
      open={targetDate !== null}
      onClose={onClose}
      title={t('calendar.choiceModal.title')}
    >
      <p className="text-sm text-gray-600">{targetDate}</p>
      <div className="mt-4 flex flex-col gap-2">
        <Link to={targetDate ? ROUTES.dailyReport(targetDate) : '#'}>
          <Button className="w-full" onClick={onClose}>
            {t('calendar.choiceModal.report')}
          </Button>
        </Link>
        <Link to={targetDate ? ROUTES.dailyReportProgress(targetDate) : '#'}>
          <Button variant="secondary" className="w-full" onClick={onClose}>
            {t('calendar.choiceModal.progressOnly')}
          </Button>
        </Link>
      </div>
    </Modal>
  )
}
