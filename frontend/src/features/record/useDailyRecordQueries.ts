import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import {
  getQuota,
  getRecord,
  getScheduleItemsForReport,
  getScheduleItemsHistoryForReport,
  type DailyRecordRead,
  type GoalScheduleItemsForReportRead,
  type QuotaItemRead,
} from '../../api/records'
import {
  listActiveReadingBooks,
  listActiveWorkAssignments,
  listGoals,
  type ActiveReadingBook,
  type ActiveWorkAssignment,
  type GoalRead,
} from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'

export type DailyRecordQueries = {
  record: UseQueryResult<DailyRecordRead>
  quota: UseQueryResult<QuotaItemRead[]>
  readingBooks: UseQueryResult<ActiveReadingBook[]>
  workAssignments: UseQueryResult<ActiveWorkAssignment[]>
  goals: UseQueryResult<GoalRead[]>
  /** 「今日の作業項目」欄（開発Todo_スケジュール・ガントチャート_v1.1 D-32、単位4）。
   * SC-06・SC-07が使う。閲覧専用のSC-08（DailyReportViewPage）では取得するが描画には
   * 使わない（単位4開発Todo2章補足6、下書きhydrate/マージの既存の仕組みをそのまま
   * 再利用する利点を優先した判断）。 */
  scheduleItems: UseQueryResult<GoalScheduleItemsForReportRead[]>
  /** 確定済みの種別の読み取り専用表示用（軽微な修正3、開発Todo_スケジュール・ガントチャート_
   * 検証修正_v1.0.md）。その日に更新した行（完了・中止を含む）のみを返す。 */
  scheduleItemsHistory: UseQueryResult<GoalScheduleItemsForReportRead[]>
}

/**
 * 日次記録の入力（SC-06）・閲覧（SC-08）で共通して必要になる取得をまとめる
 * （CODING_RULES.md「①DRYの原則」。従来は DailyReportPage と DailyReportViewPage に
 * 同じ5本のuseQueryが並記されており、キーやクエリ関数の変更を2箇所へ反映する必要があった）。
 *
 * 取得の配線のみを担い、ローディング/エラー/遷移の判定は行わない。判定は画面ごとに異なり
 * （SC-06は入力可能期間・確定状況による転送を伴う）、かつ純粋関数として検証したいため、
 * resolveDailyReportGuard 等の.ts側へ置く（CODING_RULES.md「フロントの分岐は.tsへ切り出す」）。
 */
export function useDailyRecordQueries(targetDate: string): DailyRecordQueries {
  const record = useQuery({
    queryKey: QUERY_KEYS.record(targetDate),
    queryFn: () => getRecord(targetDate),
  })
  const quota = useQuery({
    queryKey: QUERY_KEYS.quota(targetDate),
    queryFn: () => getQuota(targetDate),
  })
  const readingBooks = useQuery({
    queryKey: QUERY_KEYS.activeReadingBooks(),
    queryFn: listActiveReadingBooks,
  })
  const workAssignments = useQuery({
    queryKey: QUERY_KEYS.activeWorkAssignments(),
    queryFn: listActiveWorkAssignments,
  })
  const goals = useQuery({
    queryKey: QUERY_KEYS.goals(),
    queryFn: () => listGoals(),
  })
  const scheduleItems = useQuery({
    queryKey: QUERY_KEYS.scheduleItemsForReport(targetDate),
    queryFn: () => getScheduleItemsForReport(targetDate),
  })
  const scheduleItemsHistory = useQuery({
    queryKey: QUERY_KEYS.scheduleItemsHistoryForReport(targetDate),
    queryFn: () => getScheduleItemsHistoryForReport(targetDate),
  })

  return {
    record,
    quota,
    readingBooks,
    workAssignments,
    goals,
    scheduleItems,
    scheduleItemsHistory,
  }
}
