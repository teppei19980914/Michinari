import { t } from '../../locales/t'
import type { DayType } from '../../api/calendar'

/**
 * 「今日は何もしていない」確定後に表示する文言を日種別から決める（仕様書6.5改）。
 *
 * PLAN（計画日）は「記録しました。明日また開いてください」、それ以外（BUFFER/OFF）は
 * 「今日はお休みの日です。休むことも計画のうちです」とする。BUFFER・OFFはいずれも日次
 * ノルマが0の日という点で共通するため（ロジック・プロンプト編4.2）、同じ「休みの日」文言
 * にまとめる。
 */
export function resolveZeroRecordMessage(dayType: DayType): string {
  return dayType === 'PLAN'
    ? t('dailyReport.zeroRecord.planDayMessage')
    : t('dailyReport.zeroRecord.restDayMessage')
}
