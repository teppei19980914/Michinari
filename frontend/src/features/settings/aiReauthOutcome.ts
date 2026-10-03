import type { AiLoginResult } from '../../api/ai'

export type AiReauthOutcome = 'succeeded' | 'failed'

/** 再認証ボタン押下結果を画面表示用の成否に変換する（PAT指定時は同期的にauthenticatedへ
 * 反映されるため、authenticatedの真偽のみで判定する）。 */
export function resolveReauthOutcome(result: AiLoginResult): AiReauthOutcome {
  return result.authenticated ? 'succeeded' : 'failed'
}
