/** バックアップ一覧（SC-12）のファイルサイズ表示。1000区切りではなく1024区切り
 * （バイナリ接頭辞）を用いる。KB未満はB、GB以上は出ない前提（DBファイル想定）だが
 * 念のため上位単位まで対応する。 */
const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const

export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes}B`
  }
  let value = bytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < UNITS.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(1)}${UNITS[unitIndex]}`
}
