import { useQuery } from '@tanstack/react-query'
import { getAiStatus } from '../api/ai'
import { QUERY_KEYS } from '../constants/queryKeys'

/**
 * AI接続が設定済みか（設定画面のPAT設定・認証状態、仕様書6.11・8.10）。
 *
 * AIを使う機能（フィードバック・レポート生成等）を開いたとき、未設定であればエラーではなく
 * 案内（AiUnconfiguredNotice）を表示するために使う（非エンジニア向けエラー表示改善）。
 * 取得中は「未設定」と誤判定しない（true を返す）。データが揃う前に案内が一瞬表示され、
 * 直後に本来のAI機能表示へ切り替わるちらつきを避けるため。
 */
export function useAiConfigured(): boolean {
  const { data } = useQuery({ queryKey: QUERY_KEYS.aiStatus(), queryFn: getAiStatus })
  return data?.authenticated ?? true
}
