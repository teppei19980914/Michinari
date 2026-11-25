import { useState } from 'react'
import { generateScheduleRevisionProposal } from '../../api/schedule'

export type ScheduleRevisionBannerStatus = 'generating' | 'succeeded' | 'no_proposal' | 'failed'

/**
 * 日次報告の確定後、遅れのある目標ごとに修正案の生成を依頼する（開発Todo_スケジュール・
 * ガントチャート_v1.1 13.1、単位5）。新しい常駐処理を増やさないため、画面を開いている間
 * だけ画面から依頼する（確定後に画面を閉じた場合は生成されない、13.1本文）。
 *
 * 状態は目標IDごとに保持し、`ScheduleRevisionBanner`が「作成中」「修正案があります」
 * 「作成できませんでした」を出し分ける（13.8 SC-06）。
 */
export function useScheduleRevisionBanner() {
  const [statusByGoalId, setStatusByGoalId] = useState<
    Record<number, ScheduleRevisionBannerStatus>
  >({})

  function generateForGoals(goalIds: number[], recordDate: string): void {
    for (const goalId of goalIds) {
      setStatusByGoalId((prev) => ({ ...prev, [goalId]: 'generating' }))
      generateScheduleRevisionProposal(goalId, { trigger: 'AUTO', record_date: recordDate })
        .then((result) => {
          setStatusByGoalId((prev) => ({
            ...prev,
            [goalId]: result.proposal ? 'succeeded' : 'no_proposal',
          }))
        })
        .catch(() => {
          setStatusByGoalId((prev) => ({ ...prev, [goalId]: 'failed' }))
        })
    }
  }

  return { statusByGoalId, generateForGoals }
}
