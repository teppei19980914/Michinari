/**
 * 周回別系列（品質推移・実効速度推移で共通の形状）をRechartsの1データセットへ結合する
 * （14.3「周回別に系列を分離」を、Rechartsが要求する「1行=1x値、系列ごとに別キー」の
 * 形に変換する処理。品質推移タブ・実効速度推移タブの双方で使うため共通化した、CLAUDE.md
 * DRYの原則）。
 */

export type CyclePoint = { x: string; value: number }
export type CycleSeriesInput = { cycleNumber: number; points: CyclePoint[] }
export type MergedCycleRow = { x: string; [cycleKey: string]: string | number | undefined }

export function cycleSeriesKey(cycleNumber: number): string {
  return `cycle_${cycleNumber}`
}

export function mergeCycleSeries(series: CycleSeriesInput[]): {
  rows: MergedCycleRow[]
  cycleNumbers: number[]
} {
  const xValues = new Set<string>()
  for (const s of series) {
    for (const p of s.points) {
      xValues.add(p.x)
    }
  }
  const sortedX = [...xValues].sort()
  const rowByX = new Map<string, MergedCycleRow>(sortedX.map((x) => [x, { x }]))

  for (const s of series) {
    const key = cycleSeriesKey(s.cycleNumber)
    for (const p of s.points) {
      const row = rowByX.get(p.x)
      if (row) {
        row[key] = p.value
      }
    }
  }

  return {
    rows: sortedX.map((x) => rowByX.get(x) as MergedCycleRow),
    cycleNumbers: [...series.map((s) => s.cycleNumber)].sort((a, b) => a - b),
  }
}
