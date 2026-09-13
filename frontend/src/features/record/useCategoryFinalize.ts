import { useMutation } from '@tanstack/react-query'
import type { DailyRecordRead } from '../../api/records'

export type CategoryFinalizeOptions = {
  /** 確定処理。カテゴリごとにエンドポイントと送信する下書きが異なるため呼び出し側が渡す。 */
  finalizeRequest: () => Promise<DailyRecordRead>
  /** 確定後の共通処理（キャッシュの無効化と、全カテゴリ確定時の遷移）。 */
  onFinalized: (record: DailyRecordRead) => void
  onError: (error: unknown) => void
}

export type CategoryFinalize = {
  isPending: boolean
  /** 確定を発火する（画面のボタンから呼ぶ）。 */
  submit: () => void
}

/**
 * 日次報告のカテゴリ別確定（資格試験/読書/仕事）をまとめる。
 *
 * 確定はカテゴリごとに独立しており（仕様変更2026-09-05）、送信先と送信内容だけが異なる。
 * 確定後の処理は3カテゴリで同一のため、呼び出し側から1つのonFinalizedとして受け取る
 * （CODING_RULES.md「①DRYの原則」）。
 */
export function useCategoryFinalize({
  finalizeRequest,
  onFinalized,
  onError,
}: CategoryFinalizeOptions): CategoryFinalize {
  const mutation = useMutation({
    mutationFn: finalizeRequest,
    onSuccess: onFinalized,
    onError,
  })

  return { isPending: mutation.isPending, submit: () => mutation.mutate() }
}
