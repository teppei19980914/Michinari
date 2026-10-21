/** 目標相談チャットの判定ロジック（純粋関数、S09）。
 *
 * 描画と通信はコンポーネント・フックに置き、判定はここに寄せる（CODING_RULES.md「フロントの分岐は `.ts` へ切り出す」、
 * `helpAssistantLogic.ts`と同じ方針）。文言は`ja.json`の`goalConsultation.*`から引く。 */

/** 送信前の質問の検証結果。問題が無ければnull。 */
export type QuestionError = 'empty' | 'tooLong'

/** 送信前に質問を検証する（サーバーも同じ上限で検証する。二重の防御）。 */
export function validateQuestion(text: string, maxChars: number): QuestionError | null {
  const trimmed = text.trim()
  if (trimmed.length === 0) return 'empty'
  if (trimmed.length > maxChars) return 'tooLong'
  return null
}

/** 表示できない回答（UNAVAILABLE）の固定文言のキー。ANSWEREDは本文を表示するため対象外
 * （目標相談にはヘルプのNOT_FOUNDに相当する状態は無い。根拠が無い場合もAIの本文に
 * 「記録からはまだ判断できません」と書かれるため、固定文言での上書きは不要、開発Todo U17）。 */
export const UNAVAILABLE_MESSAGE_KEY = 'goalConsultation.unavailable'

/** APIのエラーコードから、利用者へ出す文言のキーを返す。AI未接続だけを別に案内する。 */
export function errorMessageKey(code: string | undefined): string {
  return code === 'AI_AUTH_REQUIRED' ? 'goalConsultation.authRequired' : 'goalConsultation.error'
}
