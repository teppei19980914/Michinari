import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { addMonths, endOfMonth, endOfWeek, format, startOfMonth, startOfWeek, subMonths } from 'date-fns'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { getCalendar } from '../api/calendar'
import { getToday } from '../api/records'
import { listGoals, getGoal, type GoalDetailRead } from '../api/goals'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { ROUTES } from '../constants/routes'
import { CalendarGrid } from '../features/calendar/CalendarGrid'
import { DayTypeEditModal } from '../features/calendar/DayTypeEditModal'
import { resolveCalendarDateAction } from '../features/calendar/resolveCalendarDateAction'
import { resolveAuxiliaryMarkers } from '../features/calendar/resolveAuxiliaryMarkers'

async function listActiveGoalDetails(): Promise<GoalDetailRead[]> {
  const goals = await listGoals()
  const activeGoals = goals.filter((goal) => goal.status === 'ACTIVE')
  return Promise.all(activeGoals.map((goal) => getGoal(goal.id)))
}

/** SC-05 カレンダー（仕様書6.4）。日付選択時の遷移先判定は
 * features/calendar/resolveCalendarDateAction.ts に切り出している（技術選定書4.5
 * 「日付状態による遷移先の判定」）。 */
export function CalendarPage() {
  const navigate = useNavigate()
  const [month, setMonth] = useState(() => startOfMonth(new Date()))
  const [editingDayTypeDate, setEditingDayTypeDate] = useState<string | null>(null)
  const [choiceDate, setChoiceDate] = useState<string | null>(null)

  const gridStart = startOfWeek(startOfMonth(month))
  const gridEnd = endOfWeek(endOfMonth(month))
  const dateFrom = format(gridStart, 'yyyy-MM-dd')
  const dateTo = format(gridEnd, 'yyyy-MM-dd')

  const todayQuery = useQuery({ queryKey: ['today'], queryFn: getToday })
  const calendarQuery = useQuery({
    queryKey: ['calendar', dateFrom, dateTo],
    queryFn: () => getCalendar(dateFrom, dateTo),
  })
  const activeGoalsQuery = useQuery({
    queryKey: ['active-goal-details'],
    queryFn: listActiveGoalDetails,
  })

  if (todayQuery.isLoading || calendarQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (todayQuery.isError || !todayQuery.data || calendarQuery.isError || !calendarQuery.data) {
    return (
      <p className="p-6 text-sm text-red-600">
        {apiErrorMessage(todayQuery.error ?? calendarQuery.error)}
      </p>
    )
  }

  const today = todayQuery.data.logical_date
  const daysByDate = new Map(calendarQuery.data.map((day) => [day.target_date, day]))
  const auxiliaryMarkersByDate = new Map(
    [...daysByDate.keys()].map((date) => [
      date,
      resolveAuxiliaryMarkers(date, activeGoalsQuery.data ?? []),
    ]),
  )

  const handleSelectDate = (date: string) => {
    const dayInfo = daysByDate.get(date)
    const action = resolveCalendarDateAction({
      targetDate: date,
      today,
      recordState: dayInfo?.record_state ?? null,
    })
    switch (action) {
      case 'DAY_TYPE_ONLY':
        setEditingDayTypeDate(date)
        return
      case 'CHOOSE_REPORT_TYPE':
        setChoiceDate(date)
        return
      case 'REPORT_TODAY':
      case 'PROMOTE_TO_REPORT':
        navigate(ROUTES.dailyReport(date))
        return
      case 'VIEW_REPORT':
      case 'VIEW_ONLY':
        navigate(ROUTES.dailyReportView(date))
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">{t('calendar.title')}</h1>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => setMonth((m) => subMonths(m, 1))}>
            {t('calendar.prevMonth')}
          </Button>
          <span className="text-sm text-gray-700">{format(month, 'yyyy-MM')}</span>
          <Button variant="secondary" onClick={() => setMonth((m) => addMonths(m, 1))}>
            {t('calendar.nextMonth')}
          </Button>
        </div>
      </div>

      <CalendarGrid
        month={month}
        daysByDate={daysByDate}
        auxiliaryMarkersByDate={auxiliaryMarkersByDate}
        onSelectDate={handleSelectDate}
        onEditDayType={setEditingDayTypeDate}
      />

      <DayTypeEditModal targetDate={editingDayTypeDate} onClose={() => setEditingDayTypeDate(null)} />

      <Modal
        open={choiceDate !== null}
        onClose={() => setChoiceDate(null)}
        title={t('calendar.choiceModal.title')}
      >
        <p className="text-sm text-gray-600">{choiceDate}</p>
        <div className="mt-4 flex flex-col gap-2">
          <Link to={choiceDate ? ROUTES.dailyReport(choiceDate) : '#'}>
            <Button className="w-full" onClick={() => setChoiceDate(null)}>
              {t('calendar.choiceModal.report')}
            </Button>
          </Link>
          <Link to={choiceDate ? ROUTES.dailyReportProgress(choiceDate) : '#'}>
            <Button variant="secondary" className="w-full" onClick={() => setChoiceDate(null)}>
              {t('calendar.choiceModal.progressOnly')}
            </Button>
          </Link>
        </div>
      </Modal>
    </div>
  )
}
