import { differenceInCalendarDays, parseISO } from 'date-fns'

/**
 * ガントチャート（技術選定書「CSS Grid + Tailwindで自作」）の帯位置を算出する。
 * 全教材の開始日〜締切の最小・最大範囲を100%とし、各教材の帯の左端・幅・進捗の
 * 塗りつぶし幅、および本日位置を百分率で返す（描画側はこの値をwidth/left styleへ
 * そのまま渡すだけにする）。
 */

export type GanttMaterialInput = {
  material_id: number
  start_date: string
  due_date: string
  progress_rate: number
}

export type GanttLayoutEntry = {
  material_id: number
  leftPercent: number
  widthPercent: number
  progressWidthPercent: number
}

export type GanttLayout = {
  entries: GanttLayoutEntry[]
  todayPercent: number | null
}

function daysBetween(fromIso: string, toIso: string): number {
  return differenceInCalendarDays(parseISO(toIso), parseISO(fromIso))
}

function clampRate(rate: number): number {
  return Math.min(1, Math.max(0, rate))
}

export function computeGanttLayout(materials: GanttMaterialInput[], today: string): GanttLayout {
  if (materials.length === 0) {
    return { entries: [], todayPercent: null }
  }

  const rangeStart = materials.map((m) => m.start_date).sort()[0]
  const rangeEnd = materials.map((m) => m.due_date).sort().at(-1) as string
  const totalDays = daysBetween(rangeStart, rangeEnd)

  if (totalDays <= 0) {
    // 境界値: 全教材の開始日・締切が同一日など、範囲が0日の場合は全幅で表示する。
    const entries = materials.map((m) => ({
      material_id: m.material_id,
      leftPercent: 0,
      widthPercent: 100,
      progressWidthPercent: 100 * clampRate(m.progress_rate),
    }))
    return { entries, todayPercent: null }
  }

  const entries = materials.map((m) => {
    const left = daysBetween(rangeStart, m.start_date)
    const width = Math.max(daysBetween(m.start_date, m.due_date), 0)
    const widthPercent = (width / totalDays) * 100
    return {
      material_id: m.material_id,
      leftPercent: (left / totalDays) * 100,
      widthPercent,
      progressWidthPercent: widthPercent * clampRate(m.progress_rate),
    }
  })

  const todayOffset = daysBetween(rangeStart, today)
  const todayPercent =
    todayOffset >= 0 && todayOffset <= totalDays ? (todayOffset / totalDays) * 100 : null

  return { entries, todayPercent }
}
