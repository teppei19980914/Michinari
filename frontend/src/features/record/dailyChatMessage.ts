import type { ChatMessageRead } from '../../api/records'
import type { components } from '../../types/api.d.ts'

type AiPurpose = components['schemas']['AiPurpose']

export type ChatExchange = {
  /** 対話の対象目標。日次フィードバックは目標単位の会話として扱う（Phase26）。 */
  goalId: number | null
  purpose: AiPurpose
  /** 利用者の発言。初回の「フィードバックを受け取る」ボタンのようにnullのこともある。 */
  message: string | null
  assistantMessage: ChatMessageRead
}

/**
 * AI対話の1往復を表示用の履歴へ追加する（資格試験・読書・仕事の3カテゴリで共通。
 * CODING_RULES.md「①DRYの原則」）。
 *
 * ユーザー発言もサーバ側では保存されるが、レスポンスにはassistant_messageしか含まれない
 * （ChatResponseスキーマ）ため、即時表示用に正のid（サーバ採番）と衝突しない負の仮idを
 * 付けたローカル表示専用エントリを組み立てる。
 *
 * @param current 現在の表示中の履歴（purposeで3カテゴリ分が混在する）
 * @param exchange 送信した発言とAIの応答
 * @returns ユーザー発言（あれば）とAIの応答を末尾へ追加した新しい履歴
 */
export function appendChatExchange(
  current: ChatMessageRead[],
  exchange: ChatExchange,
): ChatMessageRead[] {
  // 空のメッセージ（nullおよび空文字）は表示用の発言を作らない。空文字の送信はChatPanelが
  // 抑止しているため通常は到達しないが、切り出し前の判定（truthy）をそのまま保つ。
  const userMessages: ChatMessageRead[] = !exchange.message
    ? []
    : [
          {
            id: -Date.now(),
            goal_id: exchange.goalId,
            purpose: exchange.purpose,
            role: 'USER',
            content: exchange.message,
            sequence: current.length,
            created_at: new Date().toISOString(),
          },
        ]

  return [...current, ...userMessages, exchange.assistantMessage]
}

/**
 * 表示中のカテゴリセクションに対応する対話だけを取り出す。
 *
 * chat_messagesは3カテゴリ分がpurposeで混在した1つの配列であり、さらに同じpurposeでも
 * 目標が異なる会話が混ざりうる（日次フィードバックを目標単位の会話へ分離したPhase26以降）。
 * goal_idがnullのものは目標単位への分離前に保存された記録のため、どの目標を選んでいても
 * 表示する（過去の対話が画面から消えないようにする）。
 *
 * @param messages 日次記録が持つ全対話
 * @param purpose 取り出す用途（DAILY_FEEDBACK / DAILY_FEEDBACK_READING / DAILY_FEEDBACK_WORK）
 * @param goalId 表示中のカテゴリセクションが指す目標
 */
export function filterCategoryMessages(
  messages: ChatMessageRead[],
  purpose: AiPurpose,
  goalId: number | null,
): ChatMessageRead[] {
  return messages.filter(
    (message) =>
      message.purpose === purpose && (message.goal_id === goalId || message.goal_id === null),
  )
}
