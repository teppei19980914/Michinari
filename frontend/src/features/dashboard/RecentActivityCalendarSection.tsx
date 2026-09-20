import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { getCalendar } from '../../api/calendar'
import { ROUTES } from '../../constants/routes'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { CalendarGrid } from '../calendar/CalendarGrid'
import { resolveRecentWeeksRange } from './resolveRecentWeeksRange'

const EMPTY_AUXILIARY_MARKERS = new Map()

/** 直近4週間カレンダー（仕様書6.1、S-4 4-5）。
 *
 * 月次カレンダー（SC-05）と同じCalendarGrid・日種別背景色・記録状態マーカーをそのまま
 * 再利用し、同じロジックを二重実装しない（CLAUDE.md DRYの原則）。ホーム画面向けの
 * 縮小ウィジェットのため、日種別の手動編集・日付クリックでの遷移は持たず、一覧性のみを
 * 提供する（詳しい操作は「カレンダーを見る」からSC-05へ進む）。補助表示（受験日等）は
 * 目標ごとの詳細情報の取得を必要とするため、縮小ウィジェットでは対象外とする。 */
export function RecentActivityCalendarSection({ today }: { today: string }) {
  const { dateFrom, dateTo } = resolveRecentWeeksRange(new Date(today))
  const calendarQuery = useQuery({
    queryKey: QUERY_KEYS.calendarRange(dateFrom, dateTo),
    queryFn: () => getCalendar(dateFrom, dateTo),
  })

  if (!calendarQuery.data) {
    return null
  }
  const daysByDate = new Map(calendarQuery.data.map((day) => [day.target_date, day]))

  return (
    <Card>
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="font-medium text-gray-900">{t('dashboard.recentActivityCalendar.title')}</h2>
        <Link to={ROUTES.calendar} className="text-xs text-blue-600 hover:underline">
          {t('dashboard.recentActivityCalendar.viewCalendarLink')}
        </Link>
      </div>
      <CalendarGrid
        dateFrom={dateFrom}
        dateTo={dateTo}
        daysByDate={daysByDate}
        auxiliaryMarkersByDate={EMPTY_AUXILIARY_MARKERS}
      />
    </Card>
  )
}
