/**
 * 分析画面（SC-09）のグラフ配色。dataviz skillの検証済み既定パレット（references/palette.md）
 * をそのまま採用する（カテゴリカル順序は固定、CVD安全性が検証済みのため独自配色にしない）。
 *
 * Rechartsの`stroke`はSVG属性として描画されCSS変数(`var(--...)`)を安定して解決できないため、
 * グリッド線・計画線のような「地味な中立色」は`resolve*Color()`関数で現在のテーマ
 * （`document.documentElement.dataset.theme`、UIリッチ化）を見て明暗の値を切り替える
 * （`CYCLE_SERIES_COLORS`等の系列色はCVD安全性の検証済みパレットのため明暗を問わず維持する）。
 */

function isDarkTheme(): boolean {
  return document.documentElement.dataset.theme === 'dark'
}

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
export function resolvePlanLineColor(): string {
  return isDarkTheme() ? '#9ca3af' : '#898781'
}

export function resolveGridLineColor(): string {
  return isDarkTheme() ? '#374151' : '#e1e0d9'
}

export function resolveAxisLineColor(): string {
  return isDarkTheme() ? '#4b5563' : '#c3c2b7'
}
