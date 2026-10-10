import { format, parseISO } from 'date-fns'
import { getLocale } from '../../locales/t'

/** グラフの横軸ラベルを粒度に応じて整形する（14.2の3粒度: 日別・週別・月別）。
 *
 * 日英i18n対応（2026-10）: 月表記と範囲区切り記号のみロケール分岐する。`M/d`形式の
 * 日付自体は数字のみで言語依存しないため分岐不要。 */
export function formatPeriodLabel(periodStart: string, granularity: 'DAY' | 'WEEK' | 'MONTH'): string {
  const date = parseISO(periodStart)
  if (granularity === 'MONTH') {
    return getLocale() === 'en' ? format(date, 'MMM yyyy') : format(date, 'yyyy年M月')
  }
  if (granularity === 'WEEK') {
    const rangeMarker = getLocale() === 'en' ? '–' : '〜'
    return `${format(date, 'M/d')}${rangeMarker}`
  }
  return format(date, 'M/d')
}

/** 実績日付（YYYY-MM-DD）の横軸ラベルを整形する（進捗タブ・実効速度タブで共用、
 * CLAUDE.md DRYの原則。粒度切替が無い日付軸専用のため formatPeriodLabel とは分離）。 */
export function formatDateTick(value: string): string {
  return format(parseISO(value), 'M/d')
}

/** Y軸の目盛りラベルを整形する（品質推移・進捗・実効速度タブで共用）。
 * Rechartsの既定フォーマッタは、ドメイン上限が丸め誤差を含む場合に目盛りラベルが
 * 破損すること（例: "220" が "000000001" と表示される）を実機確認したため、
 * 明示的に整数へ丸めて文字列化する防御的な実装とした（Phase9実装時の不具合対応）。 */
export function formatAxisNumber(value: number): string {
  return String(Math.round(value))
}
