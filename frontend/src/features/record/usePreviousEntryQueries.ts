import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import {
  getPreviousDiary,
  getPreviousReadingLog,
  getPreviousWorkLog,
  type PreviousEntryRead,
} from '../../api/records'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 「前回はこう書いていました」ヒント用の取得（記録画面改善タスク2026-09-17）。
 * 前回の記録が無ければサーバがnullを返す（フロントは非表示にする、PreviousEntryHint）。 */
export function usePreviousDiaryEntry(
  targetDate: string,
  goalId: number,
): UseQueryResult<PreviousEntryRead | null> {
  return useQuery({
    queryKey: QUERY_KEYS.previousDiary(targetDate, goalId),
    queryFn: () => getPreviousDiary(targetDate, goalId),
  })
}

export function usePreviousReadingLogEntry(
  targetDate: string,
  bookId: number,
): UseQueryResult<PreviousEntryRead | null> {
  return useQuery({
    queryKey: QUERY_KEYS.previousReadingLog(targetDate, bookId),
    queryFn: () => getPreviousReadingLog(targetDate, bookId),
  })
}

export function usePreviousWorkLogEntry(
  targetDate: string,
  workAssignmentId: number,
): UseQueryResult<PreviousEntryRead | null> {
  return useQuery({
    queryKey: QUERY_KEYS.previousWorkLog(targetDate, workAssignmentId),
    queryFn: () => getPreviousWorkLog(targetDate, workAssignmentId),
  })
}
