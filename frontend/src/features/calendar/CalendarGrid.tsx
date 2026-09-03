import { eachDayOfInterval, endOfMonth, endOfWeek, format, isSameMonth, startOfMonth, startOfWeek } from 'date-fns'
import { t } from '../../locales/t'
import { resolveCalendarCellBackgroundClass, resolveCalendarCellMarkerKey } from './calendarCellStyle'
import type { AttributedAuxiliaryMarker, AuxiliaryMarker } from './resolveAuxiliaryMarkers'
import { groupByGoal } from '../../utils/groupByGoal'
import type { CalendarDayRead } from '../../api/calendar'

const WEEKDAY_KEYS = [0, 1, 2, 3, 4, 5, 6] as const

const AUXILIARY_MARKER_ORDER: AuxiliaryMarker[] = ['EXAM_DATE', 'EXAM_PERIOD', 'LOAD_ADJUSTED']

type CalendarGridProps = {
  month: Date
  daysByDate: Map<string, CalendarDayRead>
  auxiliaryMarkersByDate: Map<string, AttributedAuxiliaryMarker[]>
  onSelectDate: (date: string) => void
  onEditDayType: (date: string) => void
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
  month,
  daysByDate,
  auxiliaryMarkersByDate,
  onSelectDate,
  onEditDayType,
}: CalendarGridProps) {
  const gridStart = startOfWeek(startOfMonth(month))
  const gridEnd = endOfWeek(endOfMonth(month))
  const days = eachDayOfInterval({ start: gridStart, end: gridEnd })

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
        const isCurrentMonth = isSameMonth(day, month)

        return (
          <div
            key={dateKey}
            className={`flex min-h-16 flex-col justify-between rounded-md border border-gray-200 p-1 text-xs ${
              dayInfo ? resolveCalendarCellBackgroundClass(dayInfo.day_type) : 'bg-white'
            } ${isCurrentMonth ? '' : 'opacity-40'}`}
          >
            <button
              type="button"
              className="text-left font-medium text-gray-900 hover:underline"
              onClick={() => onSelectDate(dateKey)}
            >
              {format(day, 'd')}
            </button>
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
            <button
              type="button"
              className="self-end text-[10px] text-gray-400 hover:text-gray-600"
              onClick={() => onEditDayType(dateKey)}
            >
              {t('calendar.editDayTypeLink')}
            </button>
          </div>
        )
      })}
    </div>
  )
}
