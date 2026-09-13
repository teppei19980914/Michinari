import type { QueryClient } from '@tanstack/react-query'
import { QUERY_KEYS } from '../../constants/queryKeys'

/**
 * 日次記録を更新（確定・進捗のみ登録）した後に作り直す必要のあるキャッシュをまとめて無効化する。
 *
 * 対象は「その日の記録そのもの」と、その記録を集計・参照している画面である。日次報告（SC-06）
 * と進捗のみ登録（SC-07）で同じ4件を無効化しており、従来は両画面に同じ4行が書かれていた。
 * 無効化対象を1つ増やしたときに片方だけ直すと、更新したのに古い値が残る画面ができるため
 * 1箇所へ集約する（CODING_RULES.md「①DRYの原則」）。
 *
 * @param queryClient 無効化するキャッシュを持つクライアント
 * @param targetDate 更新した記録の日付（YYYY-MM-DD）
 */
export function invalidateDailyRecordCaches(queryClient: QueryClient, targetDate: string): void {
  queryClient.invalidateQueries({ queryKey: QUERY_KEYS.record(targetDate) })
  // 本日の報告状況（ダッシュボードの導線）と、月次の記録状況（カレンダー）も変化する。
  queryClient.invalidateQueries({ queryKey: QUERY_KEYS.today() })
  queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboard() })
  queryClient.invalidateQueries({ queryKey: QUERY_KEYS.calendar() })
}
