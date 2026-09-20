import { eachDayOfInterval, format, isSameMonth, parseISO } from 'date-fns'
import { t } from '../../locales/t'
import { resolveCalendarCellBackgroundClass, resolveCalendarCellMarkerKey } from './calendarCellStyle'
import type { AttributedAuxiliaryMarker, AuxiliaryMarker } from './resolveAuxiliaryMarkers'
import { groupByGoal } from '../../utils/groupByGoal'
import type { CalendarDayRead } from '../../api/calendar'

const WEEKDAY_KEYS = [0, 1, 2, 3, 4, 5, 6] as const

const AUXILIARY_MARKER_ORDER: AuxiliaryMarker[] = ['EXAM_DATE', 'EXAM_PERIOD', 'LOAD_ADJUSTED']

type CalendarGridProps = {
  /** グリッドに並べる日付範囲（ISO 8601、両端を含む）。呼び出し側が算出する
   * （月グリッドの範囲はuseCalendarMonth.ts、直近4週間の範囲はresolveRecentWeeksRange.ts、
   * いずれもCalendarGrid自身では算出しない。CLAUDE.md DRYの原則）。 */
  dateFrom: string
  dateTo: string
  daysByDate: Map<string, CalendarDayRead>
  auxiliaryMarkersByDate: Map<string, AttributedAuxiliaryMarker[]>
  /** 日付クリックでの遷移。月次カレンダー（SC-05）でのみ指定し、ダッシュボードの
   * 縮小ウィジェット（S-4 4-5、一覧性のみを提供する読み取り専用表示）では省略する
   * （未指定なら日付をボタンではなく単なるテキストとして表示する）。 */
  onSelectDate?: (date: string) => void
  /** 日種別の手動編集リンク。月次カレンダー（SC-05）でのみ表示し、ダッシュボードの
   * 縮小ウィジェット（S-4 4-5）では省略する（未指定なら表示しない）。 */
  onEditDayType?: (date: string) => void
  /** 指定した場合、この月に属さない日付（前後月のはみ出し分）を淡く表示する。
   * 月グリッド以外（直近4週間など、月をまたぐ表示）では指定しない。 */
  dimOutsideMonth?: Date
}

/** マーカー種別をラベルへ整形する（表示順を固定するためAUXILIARY_MARKER_ORDERで並べる）。 */
function formatMarkerLabels(markers: AuxiliaryMarker[]): string {
  return markers
    .slice()
    .sort((a, b) => AUXILIARY_MARKER_ORDER.indexOf(a) - AUXILIARY_MARKER_ORDER.indexOf(b))
    .map((marker) => t(`calendar.auxiliaryMarker.${marker}`))
    .join(' / ')
}

/** カレンダー本体（月グリッド）。表示ロジック（背景色・マーカーの判定）は
 * calendarCellStyle.ts / resolveAuxiliaryMarkers.ts に切り出し、ここでは描画のみ行う
 * （技術選定書4.5「フロントエンドの責務は表示と入力に限られる」）。 */
export function CalendarGrid({
  dateFrom,
  dateTo,
  daysByDate,
  auxiliaryMarkersByDate,
  onSelectDate,
  onEditDayType,
  dimOutsideMonth,
}: CalendarGridProps) {
  const days = eachDayOfInterval({ start: parseISO(dateFrom), end: parseISO(dateTo) })

  return (
    <div className="grid grid-cols-7 gap-1">
      {WEEKDAY_KEYS.map((weekday) => (
        <div key={weekday} className="px-1 text-center text-xs font-medium text-gray-500">
          {t(`calendar.weekday.${weekday}`)}
        </div>
      ))}
      {days.map((day) => {
        const dateKey = format(day, 'yyyy-MM-dd')
        const dayInfo = daysByDate.get(dateKey)
        const markers = auxiliaryMarkersByDate.get(dateKey) ?? []
        const isDimmed = dimOutsideMonth !== undefined && !isSameMonth(day, dimOutsideMonth)

        return (
          <div
            key={dateKey}
            className={`flex min-h-16 flex-col justify-between rounded-md border border-gray-200 p-1 text-xs ${
              dayInfo ? resolveCalendarCellBackgroundClass(dayInfo.day_type) : 'bg-white'
            } ${isDimmed ? 'opacity-40' : ''}`}
          >
            {onSelectDate ? (
              <button
                type="button"
                className="text-left font-medium text-gray-900 hover:underline"
                onClick={() => onSelectDate(dateKey)}
              >
                {format(day, 'd')}
              </button>
            ) : (
              <span className="font-medium text-gray-900">{format(day, 'd')}</span>
            )}
            {dayInfo && (
              <span className="text-[10px] text-gray-500">
                {t(resolveCalendarCellMarkerKey(dayInfo.record_state))}
              </span>
            )}
            {markers.length > 0 &&
              (() => {
                const groups = groupByGoal(markers)
                const showGoalName = groups.length > 1
                return (
                  <span className="flex flex-col text-[10px] text-blue-700">
                    {groups.map((group) => (
                      <span key={group.goalId}>
                        {showGoalName && `${group.goalName}: `}
                        {formatMarkerLabels(group.items.map((item) => item.marker))}
                      </span>
                    ))}
                  </span>
                )
              })()}
            {onEditDayType && (
              <button
                type="button"
                className="self-end text-[10px] text-gray-400 hover:text-gray-600"
                onClick={() => onEditDayType(dateKey)}
              >
                {t('calendar.editDayTypeLink')}
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
