/** 添付ファイル選択の判定ロジック（純粋関数、開発Todo_添付ファイル機能_v1.0）。
 *
 * 描画と通信はコンポーネント・フックに置き、判定はここに寄せる（CODING_RULES.md「フロントの
 * 分岐は `.ts` へ切り出す」）。選択中ファイルの合計文字数は、全体のプロンプト文字数上限
 * （`ai.max_prompt_chars`）の一部を占めるに過ぎないため、ここでは「極端に多すぎないか」の
 * 目安としてサーバの`ai.attachment_max_file_chars`（1ファイル上限）の件数倍を仮の目安に
 * せず、単純に選択ファイルの合計文字数を表示するところまでに留める（実際の上限判定は
 * 送信時にサーバ側が行う、A6「上限超過時は送信中止」）。 */
import type { AttachmentRead } from '../../api/attachment'

/** 選択中の添付ファイルの合計文字数。 */
export function totalSelectedChars(
  attachments: AttachmentRead[],
  selectedIds: number[],
): number {
  const byId = new Map(attachments.map((entry) => [entry.id, entry] as const))
  return selectedIds.reduce((sum, id) => sum + (byId.get(id)?.char_count ?? 0), 0)
}

/** 登録済み件数が上限に達しているか（A10、これ以上アップロードできない状態かの判定）。 */
export function isAtMaxCount(currentCount: number, maxCount: number): boolean {
  return currentCount >= maxCount
}
