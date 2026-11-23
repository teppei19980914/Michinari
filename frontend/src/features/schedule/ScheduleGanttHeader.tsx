import { addDays, format, getDate, getDay, getMonth, getYear, parseISO } from 'date-fns'
import { getLocale, t } from '../../locales/t'
import { daysBetween } from '../../utils/dateRange'

/** 日の数字セルの背景トークン（D-21「土曜日と、日曜日・祝日（同じ色）を色分けする」）。
 * `scheduleGanttGeometry.computeDayTypeRuns`の帯用の判定と同じ考え方（土曜/日曜祝日/平日）。 */
function dayHeaderBgClassName(date: Date, holidayIsoDates: ReadonlySet<string>): string {
  const iso = format(date, 'yyyy-MM-dd')
  if (holidayIsoDates.has(iso) || getDay(date) === 0) {
    return 'bg-schedule-holiday-bg'
  }
  if (getDay(date) === 6) {
    return 'bg-schedule-saturday-bg'
  }
  return ''
}

type MonthHeaderCell = { key: string; label: string; leftRem: number; widthRem: number }

function monthLabel(date: Date): string {
  return getLocale() === 'en' ? format(date, 'MMM yyyy') : format(date, 'yyyy年M月')
}

function buildMonthCells(rangeStartIso: string, totalDays: number, dayWidthRem: number): MonthHeaderCell[] {
  const cells: MonthHeaderCell[] = []
  let groupStartOffset = 0
  let groupYearMonth = ''

  for (let offset = 0; offset < totalDays; offset += 1) {
    const date = addDays(parseISO(rangeStartIso), offset)
    const yearMonth = `${getYear(date)}-${getMonth(date)}`
    if (offset === 0) {
      groupYearMonth = yearMonth
      continue
    }
    if (yearMonth !== groupYearMonth) {
      cells.push({
        key: `${groupYearMonth}-${groupStartOffset}`,
        label: monthLabel(addDays(parseISO(rangeStartIso), groupStartOffset)),
        leftRem: groupStartOffset * dayWidthRem,
        widthRem: (offset - groupStartOffset) * dayWidthRem,
      })
      groupStartOffset = offset
      groupYearMonth = yearMonth
    }
  }
  cells.push({
    key: `${groupYearMonth}-${groupStartOffset}`,
    label: monthLabel(addDays(parseISO(rangeStartIso), groupStartOffset)),
    leftRem: groupStartOffset * dayWidthRem,
    widthRem: (totalDays - groupStartOffset) * dayWidthRem,
  })
  return cells
}

function buildUncoveredYears(
  rangeStartIso: string,
  rangeEndIso: string,
  holidayYearFrom: number | null,
  holidayYearTo: number | null,
): number[] {
  const startYear = getYear(parseISO(rangeStartIso))
  const endYear = getYear(parseISO(rangeEndIso))
  const years: number[] = []
  for (let year = startYear; year <= endYear; year += 1) {
    if (holidayYearFrom === null || holidayYearTo === null || year < holidayYearFrom || year > holidayYearTo) {
      years.push(year)
    }
  }
  return years
}

/**
 * ガントの日付見出し（D-21：年月の段と日の段の2段）と、収録範囲外の年の注記（D-45）。
 * 日の段は1日ごとにラベル（数字）を表示する必要があるためDOM要素を日数分持つが、これは
 * 見出し行1行分のみであり、3.4が禁止する「100行×数百日」の積にはならない。
 */
export function ScheduleGanttHeader({
  rangeStartIso,
  rangeEndIso,
  dayWidthRem,
  holidayIsoDates,
  holidayYearFrom,
  holidayYearTo,
}: {
  rangeStartIso: string
  rangeEndIso: string
  dayWidthRem: number
  holidayIsoDates: ReadonlySet<string>
  holidayYearFrom: number | null
  holidayYearTo: number | null
}) {
  const totalDays = daysBetween(rangeStartIso, rangeEndIso) + 1
  const monthCells = buildMonthCells(rangeStartIso, totalDays, dayWidthRem)
  const uncoveredYears = buildUncoveredYears(rangeStartIso, rangeEndIso, holidayYearFrom, holidayYearTo)

  return (
    <div>
      {uncoveredYears.map((year) => (
        <p key={year} className="text-xs text-warning-text-subtle">
          {t('schedule.gantt.uncoveredYearNotice', { year })}
        </p>
      ))}
      <div className="relative h-5" style={{ width: `${totalDays * dayWidthRem}rem` }}>
        {monthCells.map((cell) => (
          <div
            key={cell.key}
            className="absolute truncate border-l border-border text-xs text-text-secondary"
            style={{ left: `${cell.leftRem}rem`, width: `${cell.widthRem}rem` }}
          >
            {cell.label}
          </div>
        ))}
      </div>
      <div className="relative h-5" style={{ width: `${totalDays * dayWidthRem}rem` }}>
        {Array.from({ length: totalDays }, (_, offset) => {
          const date = addDays(parseISO(rangeStartIso), offset)
          return (
            <div
              key={offset}
              className={`absolute border-l border-border text-center text-xs text-text-faint ${dayHeaderBgClassName(date, holidayIsoDates)}`}
              style={{ left: `${offset * dayWidthRem}rem`, width: `${dayWidthRem}rem` }}
            >
              {getDate(date)}
            </div>
          )
        })}
      </div>
    </div>
  )
}
