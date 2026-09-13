import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { addMonths, endOfMonth, endOfWeek, format, startOfMonth, startOfWeek, subMonths } from 'date-fns'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { getCalendar } from '../api/calendar'
import { getToday } from '../api/records'
import { listGoals, getGoal } from '../api/goals'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { ROUTES } from '../constants/routes'
import { CalendarGrid } from '../features/calendar/CalendarGrid'
import { DayTypeEditModal } from '../features/calendar/DayTypeEditModal'
import { resolveCalendarDateAction } from '../features/calendar/resolveCalendarDateAction'
import { resolveAuxiliaryMarkers } from '../features/calendar/resolveAuxiliaryMarkers'
import { GoalTabBar } from '../features/record/GoalTabBar'
import { useGoalReportTabs } from '../features/record/useGoalReportTabs'
import { resolveTargetGoalId } from '../features/record/resolveTargetGoalId'
import { QUERY_KEYS } from '../constants/queryKeys'

/** SC-05 カレンダー（仕様書6.4）。日付選択時の遷移先判定は
 * features/calendar/resolveCalendarDateAction.ts に切り出している（技術選定書4.5
 * 「日付状態による遷移先の判定」）。
 *
 * 補助表示（受験日・受験期間・負荷係数が1.0以外の期間。仕様書6.4の3種のみで、読書の
 * 読了目標日・仕事の案件はカレンダーの補助表示の対象外）は、日次報告（DailyReportPage）と同じGoalTabBarで
 * 選択した1目標分のみを表示する方式に統一した（Phase25、進行中の全目標を1画面に
 * 集約表示していた旧仕様6.4を改訂）。日種別・記録状態（背景色・マーカー）は
 * 目標に紐づかないアプリ全体の値のため、この目標切り替えの影響を受けない。 */
export function CalendarPage() {
  const navigate = useNavigate()
  const [month, setMonth] = useState(() => startOfMonth(new Date()))
  const [editingDayTypeDate, setEditingDayTypeDate] = useState<string | null>(null)
  const [choiceDate, setChoiceDate] = useState<string | null>(null)

  const gridStart = startOfWeek(startOfMonth(month))
  const gridEnd = endOfWeek(endOfMonth(month))
  const dateFrom = format(gridStart, 'yyyy-MM-dd')
  const dateTo = format(gridEnd, 'yyyy-MM-dd')

  const todayQuery = useQuery({ queryKey: QUERY_KEYS.today(), queryFn: getToday })
  const calendarQuery = useQuery({
    queryKey: QUERY_KEYS.calendarRange(dateFrom, dateTo),
    queryFn: () => getCalendar(dateFrom, dateTo),
  })
  const goalsQuery = useQuery({ queryKey: QUERY_KEYS.goals(), queryFn: () => listGoals() })
  const goalTabs = useGoalReportTabs(goalsQuery.data ?? [])
  const { reportableGoals, showGoalSelector, selectedGoalId, setSelectedGoalId } = goalTabs

  useEffect(() => {
    if (selectedGoalId === null && reportableGoals.length > 0) {
      setSelectedGoalId(reportableGoals[0].id)
    }
  }, [reportableGoals, selectedGoalId, setSelectedGoalId])

  const targetGoalId = resolveTargetGoalId(goalTabs)
  const selectedGoalDetailQuery = useQuery({
    queryKey: QUERY_KEYS.goal(targetGoalId),
    queryFn: () => getGoal(targetGoalId as number),
    enabled: targetGoalId !== null,
  })

  if (todayQuery.isLoading || calendarQuery.isLoading || goalsQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (
    todayQuery.isError ||
    !todayQuery.data ||
    calendarQuery.isError ||
    !calendarQuery.data ||
    goalsQuery.isError
  ) {
    // goalsQueryが失敗すると対象目標を解決できず補助表示が常に空になってしまうため、
    // 他の必須クエリと同様にエラー画面を表示する。
    return (
      <p className="p-6 text-sm text-red-600">
        {apiErrorMessage(todayQuery.error ?? calendarQuery.error ?? goalsQuery.error)}
      </p>
    )
  }

  const today = todayQuery.data.logical_date
  const daysByDate = new Map(calendarQuery.data.map((day) => [day.target_date, day]))
  const activeGoalDetails = selectedGoalDetailQuery.data ? [selectedGoalDetailQuery.data] : []
  const auxiliaryMarkersByDate = new Map(
    [...daysByDate.keys()].map((date) => [date, resolveAuxiliaryMarkers(date, activeGoalDetails)]),
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
      case 'REGISTER_PROGRESS_ONLY':
        navigate(ROUTES.dailyReportProgress(date))
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

      {showGoalSelector && (
        <GoalTabBar
          goals={reportableGoals}
          selectedGoalId={selectedGoalId}
          onSelect={setSelectedGoalId}
        />
      )}

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
