import { useState } from 'react'
import type { ScheduleRevisionDecisionsResponse } from '../../api/schedule'

/**
 * 判断API（decide）が13.5の制約で行単位にブロックした結果（`blocked_reason`、修正1
 * 開発Todo_スケジュール・ガントチャート_検証修正_v1.0.md）を、行IDごとに判定する。
 *
 * STALE（`is_stale`）とは異なり、サーバーの応答で初めて分かる（日付を直接比較できない）
 * ため、`GET /schedule`の再取得では消えない専用の状態として`ScheduleTab`が持つ。利用者が
 * 日付を修正すれば再度承認できるよう、理由を表示したままボタンは無効化しない
 * （`ScheduleRevisionChangeRow`側の責務）。
 *
 * `clearReason`で消した行は、次に新しい`outcomes`（新しい判断APIの応答）が来るまで
 * 理由を表示しない。`outcomes`自体には最新の応答しか載らないため、「解消済み」の記録を
 * レンダー中にリセットする（Effectではなく、propの変化に応じてレンダー中にstateを
 * 調整するReact公式パターン。https://react.dev/learn/you-might-not-need-an-effect）。
 */
export function useScheduleRevisionBlockedReasons(
  outcomes: ScheduleRevisionDecisionsResponse['outcomes'] | undefined,
) {
  const [prevOutcomes, setPrevOutcomes] = useState(outcomes)
  const [clearedItemIds, setClearedItemIds] = useState<ReadonlySet<number>>(new Set())

  if (outcomes !== prevOutcomes) {
    setPrevOutcomes(outcomes)
    setClearedItemIds(new Set())
  }

  function reasonFor(proposalItemId: number): string | null {
    if (clearedItemIds.has(proposalItemId)) return null
    const outcome = outcomes?.find((item) => item.proposal_item_id === proposalItemId)
    if (outcome && !outcome.applied && outcome.blocked_reason === 'INVALID_PLANNED_DATE') {
      return outcome.blocked_reason
    }
    return null
  }

  function clearReason(proposalItemId: number) {
    setClearedItemIds((prev) => {
      if (prev.has(proposalItemId)) return prev
      return new Set(prev).add(proposalItemId)
    })
  }

  return { reasonFor, clearReason }
}
