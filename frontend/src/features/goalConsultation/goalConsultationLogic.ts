/** 目標相談チャットの判定ロジック（純粋関数、S09で導入・S10で質問例ボタンを追加）。
 *
 * 描画と通信はコンポーネント・フックに置き、判定はここに寄せる（CODING_RULES.md「フロントの分岐は `.ts` へ切り出す」、
 * `helpAssistantLogic.ts`と同じ方針）。文言は`ja.json`の`goalConsultation.*`から引く。 */
import type { GoalCategory } from '../../api/goals'

/** 目標の種類ごとの質問例（ロケールキーのみ。文言自体はja.json/en.jsonで解決する、
 * CODING_RULES.mdゼロハードコーディング）。利用者確認済みの初期案（開発Todo v1.1 V12）。 */
const QUESTION_EXAMPLE_KEYS: Record<GoalCategory, string[]> = {
  EXAM: [
    'goalConsultation.questionExamples.exam1',
    'goalConsultation.questionExamples.exam2',
    'goalConsultation.questionExamples.exam3',
  ],
  READING: [
    'goalConsultation.questionExamples.reading1',
    'goalConsultation.questionExamples.reading2',
  ],
  WORK: [
    'goalConsultation.questionExamples.work1',
    'goalConsultation.questionExamples.work2',
  ],
}

/** 目標の種類に応じた質問例ボタンのロケールキー一覧を返す（開発Todo v1.1 要件2）。 */
export function questionExampleKeys(category: GoalCategory): string[] {
  return QUESTION_EXAMPLE_KEYS[category]
}

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

/** 会話の表示名（S11、開発Todo v1.2 W7）。利用者が付けた`title`があればそれを使い、
 * 空（既定）の場合はnullを返す。呼び出し側（コンポーネント）が、連番を使った既定文言
 * （`goalConsultation.conversation.untitled`）で補う。 */
export function conversationDisplayTitle(title: string): string | null {
  const trimmed = title.trim()
  return trimmed === '' ? null : trimmed
}
