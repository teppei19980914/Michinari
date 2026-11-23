import { addDays, formatISO, getDay, parseISO } from 'date-fns'
import type { components } from '../../types/api.d.ts'
import { daysBetween } from '../../utils/dateRange'

type ScheduleItemStatus = components['schemas']['ScheduleItemStatus']

export type ScheduleGanttItemInput = {
  status: ScheduleItemStatus
  planned_start_date: string
  planned_end_date: string
  actual_start_date: string | null
  actual_end_date: string | null
}

export type DateRangeIso = { startIso: string; endIso: string }

export type BandRem = { leftRem: number; widthRem: number }

export type DayTypeRun = { type: 'saturday' | 'holiday'; leftRem: number; widthRem: number }

/**
 * 表示期間（開発Todo_スケジュール・ガントチャート_v1.1 3.4）：全行の予定開始日・予定終了日・
 * 実績開始日・実績終了日と本日のうち、最も早い日から最も遅い日までとする。行が1件も無い
 * 場合は本日のみの1日を返す（空のときの案内〈D-28〉が表示されるため実際には使われない）。
 *
 * 予定日は必須のためこの関数は常に値を持つ日付のみを見る（本書3.4の「予定日が未入力の行」は
 * 単位2のNOT NULL制約と矛盾するため対象外。開発Todo_スケジュール・ガントチャート_単位3_v1.0
 * 第2章食い違い1）。
 */
export function computeDisplayRange(items: ScheduleGanttItemInput[], today: string): DateRangeIso {
  const dates: string[] = [today]
  for (const item of items) {
    dates.push(item.planned_start_date, item.planned_end_date)
    if (item.actual_start_date) dates.push(item.actual_start_date)
    if (item.actual_end_date) dates.push(item.actual_end_date)
  }
  dates.sort()
  return { startIso: dates[0], endIso: dates[dates.length - 1] }
}

/** 表示期間の日数（両端を含む）。 */
export function countDaysInclusive(range: DateRangeIso): number {
  return daysBetween(range.startIso, range.endIso) + 1
}

/**
 * 1日分の幅（rem、D-20）。コンテナ幅÷表示期間の日数を、下限・上限（app_settingの値）の
 * 範囲へクランプする。
 */
export function computeDayWidthRem(
  totalDays: number,
  containerWidthRem: number,
  minRem: number,
  maxRem: number,
): number {
  if (totalDays <= 0) {
    return maxRem
  }
  const raw = containerWidthRem / totalDays
  return Math.min(maxRem, Math.max(minRem, raw))
}

/** 表示期間の開始日からの位置を基準に、指定した日付区間の帯の位置・幅（rem）を算出する。 */
export function computeBandRem(
  rangeStartIso: string,
  startIso: string,
  endIso: string,
  dayWidthRem: number,
): BandRem {
  const leftRem = daysBetween(rangeStartIso, startIso) * dayWidthRem
  const widthRem = (daysBetween(startIso, endIso) + 1) * dayWidthRem
  return { leftRem, widthRem: Math.max(widthRem, 0) }
}

/**
 * 実績帯の区間（D-17）。進行中で実績終了日がない行は本日まで伸ばす。未着手・実績日の無い
 * 中止の行は実績帯を持たない（null）。
 */
export function computeActualBandRange(
  item: ScheduleGanttItemInput,
  today: string,
): { startIso: string; endIso: string } | null {
  if (item.status === 'DONE' && item.actual_start_date && item.actual_end_date) {
    return { startIso: item.actual_start_date, endIso: item.actual_end_date }
  }
  if (item.status === 'IN_PROGRESS' && item.actual_start_date) {
    return { startIso: item.actual_start_date, endIso: today }
  }
  if (item.status === 'CANCELLED' && item.actual_start_date) {
    return { startIso: item.actual_start_date, endIso: item.actual_end_date ?? item.actual_start_date }
  }
  return null
}

/** 本日線の位置（rem、表示期間の開始日からの左端位置。セルの中央に合わせる）。 */
export function computeTodayLineLeftRem(
  rangeStartIso: string,
  today: string,
  dayWidthRem: number,
): number {
  return daysBetween(rangeStartIso, today) * dayWidthRem + dayWidthRem / 2
}

/**
 * 土日祝の網掛け（3.4「グリッド全体に1回だけ重ねて描く」）。日ごとのDOM要素ではなく、
 * 連続する同種の日をまとめた矩形（rem）のリストを返す（100行×数百日でも要素数は区間数のみ）。
 */
export function computeDayTypeRuns(
  rangeStartIso: string,
  rangeEndIso: string,
  holidayIsoDates: ReadonlySet<string>,
  dayWidthRem: number,
): DayTypeRun[] {
  const totalDays = daysBetween(rangeStartIso, rangeEndIso) + 1
  if (totalDays <= 0) {
    return []
  }

  const runs: DayTypeRun[] = []
  let runStart = 0
  let runType: 'saturday' | 'holiday' | null = null

  const dayTypeAt = (dayOffset: number): 'saturday' | 'holiday' | null => {
    const iso = formatISO(addDays(parseISO(rangeStartIso), dayOffset), { representation: 'date' })
    if (holidayIsoDates.has(iso) || getDay(parseISO(iso)) === 0) {
      return 'holiday'
    }
    if (getDay(parseISO(iso)) === 6) {
      return 'saturday'
    }
    return null
  }

  const flush = (endOffsetExclusive: number) => {
    if (runType === null) return
    runs.push({
      type: runType,
      leftRem: runStart * dayWidthRem,
      widthRem: (endOffsetExclusive - runStart) * dayWidthRem,
    })
  }

  for (let offset = 0; offset < totalDays; offset += 1) {
    const type = dayTypeAt(offset)
    if (type !== runType) {
      flush(offset)
      runStart = offset
      runType = type
    }
  }
  flush(totalDays)

  return runs
}

/** 初期のスクロール位置（D-23）。本日が固定列のすぐ右に来る位置を基準に、右端を超えない。 */
export function computeInitialScrollLeftRem(
  todayLeftRem: number,
  totalWidthRem: number,
  viewportWidthRem: number,
): number {
  const maxScrollLeftRem = Math.max(0, totalWidthRem - viewportWidthRem)
  return Math.min(Math.max(0, todayLeftRem), maxScrollLeftRem)
}
