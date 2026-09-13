import { useState, type Dispatch, type SetStateAction } from 'react'
import { useMutation } from '@tanstack/react-query'
import type { ChatMessageRead, ChatResponse } from '../../api/records'
import type { components } from '../../types/api.d.ts'
import { appendChatExchange } from './dailyChatMessage'

type AiPurpose = components['schemas']['AiPurpose']

export type CategoryChatOptions = {
  /** 対話の対象目標（表示中のカテゴリセクションが指す1目標。resolveCategoryGoalId）。 */
  goalId: number | null
  /** 履歴の絞り込みと、ローカル表示用ユーザー発言に付与する用途。 */
  purpose: AiPurpose
  /** 送信処理。カテゴリごとにエンドポイントと下書きの積み方が異なるため呼び出し側が渡す。 */
  sendRequest: (message: string | null) => Promise<ChatResponse>
  /** 表示中の対話履歴。3カテゴリ分が1つの配列に混在するため、呼び出し側の状態を更新する。 */
  setMessages: Dispatch<SetStateAction<ChatMessageRead[]>>
  onError: (error: unknown) => void
}

export type CategoryChat = {
  isPending: boolean
  /** プロンプトが長すぎて一部が省略されたか（仕様書6.5「truncatedNotice」）。 */
  wasTruncated: boolean
  send: (message: string | null) => void
}

/**
 * 日次報告のカテゴリ別AI対話（資格試験/読書/仕事）の送信と履歴更新をまとめる。
 *
 * 3カテゴリは送信先エンドポイントと下書きの積み方だけが異なり、応答後の処理
 * （ユーザー発言の即時表示・AI応答の追加・省略通知の保持・エラー通知）は同一である。
 * 従来はこの同一処理がuseMutationごとに3回書かれていた（CODING_RULES.md「①DRYの原則」）。
 *
 * 対話は下書きをプロンプトへ渡すのみで永続化しないため、ローカルstateを常に正とする
 * （仕様書16.7「AI呼び出しが失敗しても実績入力が失われない」）。
 */
export function useCategoryChat({
  goalId,
  purpose,
  sendRequest,
  setMessages,
  onError,
}: CategoryChatOptions): CategoryChat {
  const [wasTruncated, setWasTruncated] = useState(false)

  const mutation = useMutation({
    mutationFn: sendRequest,
    onSuccess: (response, message) => {
      setMessages((current) =>
        appendChatExchange(current, {
          goalId,
          purpose,
          message,
          assistantMessage: response.assistant_message,
        }),
      )
      setWasTruncated(response.was_truncated)
    },
    onError,
  })

  return { isPending: mutation.isPending, wasTruncated, send: mutation.mutate }
}
