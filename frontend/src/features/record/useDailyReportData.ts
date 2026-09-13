import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { getToday, type TodayRead } from '../../api/records'
import { useDailyRecordQueries, type DailyRecordQueries } from './useDailyRecordQueries'
import { useSlotNames } from './useSlotNames'

export type DailyReportQueries = DailyRecordQueries & {
  today: UseQueryResult<TodayRead>
}

export type DailyReportData = {
  /** 画面の表示可否（ローディング/エラー/転送）を左右する取得。resolveDailyReportGuardへ渡す。 */
  queries: DailyReportQueries
  /** 「他の時間枠を追加」の候補。表示可否の判定には関与しない（useSlotNamesのコメント参照）。 */
  slotNames: Map<number, string>
}

/**
 * SC-06 日次報告（DailyReportPage）が必要とする取得をまとめる。
 *
 * 判定に関与する取得（queries）と、取得できなくても入力を続行できる補助情報（slotNames）を
 * 別のフィールドとして返す。両者を同じ配列・同じオブジェクトへ混ぜると、ローディング判定を
 * 「全クエリ」へ機械的に広げた際にslotNamesまで待ってしまい、入力開始が遅れるためである。
 */
export function useDailyReportData(targetDate: string): DailyReportData {
  const recordQueries = useDailyRecordQueries(targetDate)
  // 入力可能期間（当日・前日）の判定に使う論理的な本日。クライアント側で現在日時から
  // 算出してはならない（技術選定書7.1「禁止事項」）ため、サーバのGET /records/todayから取得する。
  const today = useQuery({ queryKey: ['today'], queryFn: getToday })
  const slotNames = useSlotNames()

  return { queries: { ...recordQueries, today }, slotNames }
}
