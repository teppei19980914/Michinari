import { isFinalizableDate, isFutureDate } from '../record/finalizableDate'
import type { components } from '../../types/api.d.ts'

type RecordState = components['schemas']['RecordState']

export type CalendarDateAction =
  | 'CHOOSE_REPORT_TYPE'
  | 'PROMOTE_TO_REPORT'
  | 'REGISTER_PROGRESS_ONLY'
  | 'VIEW_ONLY'
  | 'VIEW_REPORT'
  | 'REPORT_TODAY'
  | 'DAY_TYPE_ONLY'

/**
 * カレンダーの日付選択時の遷移先を判定する（仕様書6.4 SC-05「操作」表、7.2「日付の記録状態
 * 遷移」）。
 *
 * 判定は「記録状態」ではなく「対象日が入力可能期間（当日・前日、仕様書7.2）内か」を先に
 * 確定させる（仕様書1.1（改20））。recordStateは3カテゴリ（資格試験・読書・仕事）の集約値で
 * あり、未着手のカテゴリを判定から除外する（7.2）。そのため1カテゴリだけ確定した日も
 * 「報告済」となり、以前のように報告済を最優先で閲覧画面へ振ると、同じ日の残りのカテゴリを
 * 報告する手段が画面から失われていた。集約値は表示（マーカー・本日の状態）のための派生値で
 * あり、確定可否の判定には使わない。
 *
 * 入力可能期間内は日次報告画面へ進ませ、「全カテゴリ確定済みなら閲覧のみ」の判定は日次報告
 * 画面（DailyReportPage）のisAllCategoriesReportedに一任する。カレンダーAPIはカテゴリ別の
 * 確定状態を持たず、判定に必要な着手中の目標・書籍・案件も取得しないため、判定を2箇所に
 * 分散させないための方針である（DRYの原則、CODING_RULES.md「①DRYの原則」）。
 *
 * 2日以上前は確定できない（7.2）ため、未入力なら進捗のみ登録（未来日以外は登録可能）へ直接
 * 誘導する。以前は日次報告との選択モーダルを出していたが、日次報告を選んでも確定時に
 * BACKDATE_LIMIT_EXCEEDEDとなり入力内容が失われていた（仕様書6.4「未入力かつ前日以前」と
 * 7.2「当日または前日」の不整合。仕様書1.1（改20）で6.4を7.2に合わせて改訂）。
 */
export function resolveCalendarDateAction(params: {
  targetDate: string
  today: string
  recordState: RecordState | null
}): CalendarDateAction {
  const { targetDate, today, recordState } = params

  if (isFutureDate(targetDate, today)) {
    return 'DAY_TYPE_ONLY'
  }

  if (isFinalizableDate(targetDate, today)) {
    // 当日・前日。記録状態によらず日次報告へ進める（未入力の前日のみ、進捗のみ登録との
    // 選択肢を示す。仕様書6.4「未入力かつ前日」）。targetDate・todayはいずれもサーバ由来の
    // ISO日付（YYYY-MM-DD）のため、当日判定は文字列一致で足りる（Dateへの変換を挟まない）。
    if (targetDate === today) {
      return 'REPORT_TODAY'
    }
    return recordState === null ? 'CHOOSE_REPORT_TYPE' : 'PROMOTE_TO_REPORT'
  }

  // 2日以上前。確定はできないため、記録があれば閲覧、無ければ進捗のみ登録へ誘導する。
  if (recordState === 'REPORTED') {
    return 'VIEW_REPORT'
  }
  if (recordState === 'PROGRESS_ONLY') {
    return 'VIEW_ONLY'
  }
  return 'REGISTER_PROGRESS_ONLY'
}
