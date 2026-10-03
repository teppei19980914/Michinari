/**
 * 分析画面（SC-09）のグラフ配色。dataviz skillの検証済み既定パレット（references/palette.md）
 * をそのまま採用する（カテゴリカル順序は固定、CVD安全性が検証済みのため独自配色にしない）。
 * 本アプリはダークモード切替を持たない（既存の全画面がライト固定のTailwindクラスのため、
 * この画面のみダークモード対応を追加すると一貫性が崩れる）。
 */

/** 周回別系列の色（cycle_numberの昇順で固定順に割り当てる。カテゴリカルなので循環割当はしない）。 */
export const CYCLE_SERIES_COLORS = [
  '#2a78d6', // 1周目: blue
  '#eb6834', // 2周目: orange
  '#1baf7a', // 3周目: aqua
  '#eda100', // 4周目: yellow
  '#e87ba4', // 5周目: magenta
  '#008300', // 6周目: green
  '#4a3aa7', // 7周目: violet
  '#e34948', // 8周目: red
] as const

export function cycleSeriesColor(index: number): string {
  return CYCLE_SERIES_COLORS[index % CYCLE_SERIES_COLORS.length]
}

/** 合格基準線・目標到達期限など「クリアすべき基準」を示す参照線の色（statusのcritical）。 */
export const THRESHOLD_LINE_COLOR = '#d03b3b'

/** 計画線など「目標ペース」を示す参照線の色（実績と混同しないよう中立色のグレー）。 */
export const PLAN_LINE_COLOR = '#898781'

export const GRID_LINE_COLOR = '#e1e0d9'
export const AXIS_LINE_COLOR = '#c3c2b7'
