import { t } from '../../locales/t'

/** 「どのくらい前か」の表示文言を組み立てる（開発Todo_1年前の今日_v1.0 §0 V15）。
 * サーバーはmonthsAgo（整数）のみを返し、「1年前」「半年前」等の言い回しは画面文言
 * のためここ（ロケールファイル参照）で組み立てる（ゼロハードコーディング）。 */
export function resolveOnThisDayPeriodLabel(monthsAgo: number): string {
  if (monthsAgo === 6) {
    return t('dashboard.onThisDay.halfYearAgo')
  }
  if (monthsAgo % 12 === 0) {
    return t('dashboard.onThisDay.yearsAgo', { count: monthsAgo / 12 })
  }
  return t('dashboard.onThisDay.monthsAgo', { count: monthsAgo })
}
