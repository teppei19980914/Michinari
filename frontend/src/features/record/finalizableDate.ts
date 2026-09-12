import { differenceInCalendarDays } from 'date-fns'

/**
 * 報告確定（finalize）の対象日が入力可能期間内かを判定する（仕様書7.2「入力可能期間」:
 * 未入力→報告済・進捗のみ登録済→報告済はいずれも「当日または前日」）。
 *
 * バックエンドの record_service._ensure_finalizable_date と同じ規則であり、画面側では
 * 「入力させたうえで確定時に BACKDATE_LIMIT_EXCEEDED で弾く」（入力内容が失われる）事態を
 * 避けるための事前判定に用いる。カレンダーの遷移先判定（resolveCalendarDateAction）と
 * 日次報告画面のガード（DailyReportPage）の双方から参照し、期間の定義を1箇所に保つ。
 *
 * todayには必ずサーバから取得した論理的な本日（GET /records/today の logical_date）を渡す。
 * 1日の境界時刻を加味した「本日」の判定はサーバの責務であり、クライアント側で現在日時から
 * 算出してはならない（技術選定書7章「クライアント側での論理日の判断」の禁止）。
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
