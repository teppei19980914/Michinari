import { differenceInCalendarDays } from 'date-fns'
import type { components } from '../../types/api.d.ts'

type RecordState = components['schemas']['RecordState']

export type CalendarDateAction =
  | 'CHOOSE_REPORT_TYPE'
  | 'PROMOTE_TO_REPORT'
  | 'VIEW_ONLY'
  | 'VIEW_REPORT'
  | 'REPORT_TODAY'
  | 'DAY_TYPE_ONLY'

/**
 * カレンダーの日付選択時の遷移先を判定する（仕様書6.4 SC-05「操作」表、7.2「日付の記録状態
 * 遷移」）。
 *
 * 優先順位は「報告済は常に閲覧（7.2: 報告済は以降変更不可）」「未来日は日種別変更のみ」
 * 「当日は日次報告（未入力/進捗のみ登録済のいずれからでも報告へ進める）」の順に確定させ、
 * 残る過去日を「進捗のみ登録済」か「未入力」かで分岐する。仕様書6.4の6行は必ずしも
 * 排他的な条件ではない（例: 「当日」は「未入力」でも「進捗のみ登録済」でもあり得る）ため、
 * この優先順位はコード側の実装判断である。
 */
export function resolveCalendarDateAction(params: {
  targetDate: string
  today: string
  recordState: RecordState | null
}): CalendarDateAction {
  const { targetDate, today, recordState } = params

  if (recordState === 'REPORTED') {
    return 'VIEW_REPORT'
  }

  const diffFromToday = differenceInCalendarDays(new Date(targetDate), new Date(today))

  if (diffFromToday > 0) {
    return 'DAY_TYPE_ONLY'
  }
  if (diffFromToday === 0) {
    return 'REPORT_TODAY'
  }

  // diffFromToday < 0（過去日）。
  if (recordState === 'PROGRESS_ONLY') {
    return diffFromToday === -1 ? 'PROMOTE_TO_REPORT' : 'VIEW_ONLY'
  }
  return 'CHOOSE_REPORT_TYPE'
}
