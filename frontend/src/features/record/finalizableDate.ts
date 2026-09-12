import { differenceInCalendarDays } from 'date-fns'

/**
 * 日次記録の入力可能期間（仕様書7.2）を判定する純粋関数群。
 *
 * サーバ側の検証（backend/app/services/record_service.py の _ensure_finalizable_date /
 * register_progress）と同じ規則を画面側でも事前に判定するために置く。事前判定が無いと
 * 「入力させたうえで送信時にエラー（14章 BACKDATE_LIMIT_EXCEEDED 等）となり、入力内容が
 * 失われる」ため、遷移先の決定（resolveCalendarDateAction）と各入力画面のガード
 * （DailyReportPage・ProgressOnlyPage）から参照する。日付の意味付けを1箇所へ集約し、
 * 期間の定義が画面ごとにずれないようにする（DRYの原則、CODING_RULES.md「①DRYの原則」）。
 *
 * todayには必ずサーバから取得した論理的な本日（GET /records/today の logical_date）を渡す。
 * 1日の境界時刻を加味した「本日」の判定はサーバの責務であり、クライアント側で現在日時から
 * 算出してはならない（技術選定書7.1「禁止事項」）。
 */

/**
 * 報告確定（finalize）の対象日が入力可能期間内かを判定する（仕様書7.2「入力可能期間」:
 * 未入力→報告済・進捗のみ登録済→報告済はいずれも「当日または前日」）。
 *
 * @param targetDate 判定対象の日付（YYYY-MM-DD）
 * @param today サーバから取得した論理的な本日（YYYY-MM-DD）
 * @returns 対象日が当日または前日ならtrue
 * @example isFinalizableDate('2026-09-11', '2026-09-12') // => true（前日）
 * @example isFinalizableDate('2026-09-10', '2026-09-12') // => false（2日前）
 */
export function isFinalizableDate(targetDate: string, today: string): boolean {
  const diffFromToday = differenceInCalendarDays(new Date(targetDate), new Date(today))
  return diffFromToday === 0 || diffFromToday === -1
}

/**
 * 対象日が未来日かを判定する（仕様書7.2: 進捗のみ登録は「当日または前日以前」であり、
 * 未来日のみ登録できない）。確定と違って遡れる日数に上限が無いため、進捗のみ登録の
 * 可否判定はこちらを用いる。
 *
 * @param targetDate 判定対象の日付（YYYY-MM-DD）
 * @param today サーバから取得した論理的な本日（YYYY-MM-DD）
 * @returns 対象日が本日より後ならtrue
 * @example isFutureDate('2026-09-13', '2026-09-12') // => true（翌日）
 * @example isFutureDate('2026-09-12', '2026-09-12') // => false（当日）
 */
export function isFutureDate(targetDate: string, today: string): boolean {
  return differenceInCalendarDays(new Date(targetDate), new Date(today)) > 0
}
