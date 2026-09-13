/** カレンダー（SC-05）の見出しと月移動。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた CalendarPage から
 * 切り出したものである。表示中の月は useCalendarMonth.ts が保持し、ここは表示と操作の
 * 受け渡しに徹する。 */
import { format } from 'date-fns'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'

export function CalendarHeader({
  month,
  onShowPreviousMonth,
  onShowNextMonth,
}: {
  month: Date
  onShowPreviousMonth: () => void
  onShowNextMonth: () => void
}) {
  return (
    <div className="flex items-center justify-between">
      <h1 className="text-xl font-semibold text-gray-900">{t('calendar.title')}</h1>
      <div className="flex items-center gap-2">
        <Button variant="secondary" onClick={onShowPreviousMonth}>
          {t('calendar.prevMonth')}
        </Button>
        <span className="text-sm text-gray-700">{format(month, 'yyyy-MM')}</span>
        <Button variant="secondary" onClick={onShowNextMonth}>
          {t('calendar.nextMonth')}
        </Button>
      </div>
    </div>
  )
}
