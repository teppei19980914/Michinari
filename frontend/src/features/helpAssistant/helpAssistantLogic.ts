/** ヘルプAIアシスタントの判定ロジック（純粋関数、Phase43）。
 *
 * 描画と通信はコンポーネント・フックに置き、判定はここに寄せる（CODING_RULES.md「フロントの分岐は `.ts` へ切り出す」）。
 * 文言は `ja.json` の `helpAssistant.*` から引く。ここでは文言のキーだけを返す。 */
import type { HelpAnswerStatus } from '../../api/helpAssistant'

/** 送信前の質問の検証結果。問題が無ければ null。 */
export type QuestionError = 'empty' | 'tooLong'

/** 送信前に質問を検証する（サーバーも同じ上限で検証する。二重の防御）。 */
export function validateQuestion(text: string, maxChars: number): QuestionError | null {
  const trimmed = text.trim()
  if (trimmed.length === 0) return 'empty'
  if (trimmed.length > maxChars) return 'tooLong'
  return null
}

/** 記載なし・表示できない回答の固定文言のキー（ANSWERED は本文を表示するため対象外）。 */
export const FIXED_STATUS_MESSAGE_KEYS = {
  NOT_FOUND: 'helpAssistant.notFound',
  UNAVAILABLE: 'helpAssistant.unavailable',
} as const satisfies Record<Exclude<HelpAnswerStatus, 'ANSWERED'>, string>

/** API のエラーコードから、利用者へ出す文言のキーを返す。AI未接続だけを別に案内する。 */
export function errorMessageKey(code: string | undefined): string {
  return code === 'AI_AUTH_REQUIRED' ? 'helpAssistant.authRequired' : 'helpAssistant.error'
}
