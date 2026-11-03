import { useCallback, useState } from 'react'
import { celebrateMilestone, listPendingCelebrations } from '../../api/milestones'
import type { MilestoneAchievement } from '../../api/milestones'
import type { GoalCategory } from '../../api/goals'

/** キューに積む1件（目標種別はアイコン解決に必要だが、APIレスポンス自体には含まれないため
 * 取得時点〈どのカテゴリの目標を確認したか〉で付与する）。 */
export type QueuedMilestone = {
  achievement: MilestoneAchievement
  category: GoalCategory
}

export type MilestoneCelebrationQueue = {
  /** 今表示すべき節目（先頭の1件）。無ければundefined。 */
  current: QueuedMilestone | undefined
  /** 指定目標の未お祝いの節目を取得し、キューの末尾へ積む（既にキューにある節目は
   * 重複して積まない）。記録確定の直後に呼ぶ。 */
  checkGoal: (goalId: number | null | undefined, category: GoalCategory) => Promise<void>
  /** 先頭の節目をお祝い済みにして、キューから外す。通信に失敗してもキューからは外す
   * （同じ節目を繰り返し表示しないため）。失敗時は呼び出し元へ伝える。 */
  dismissCurrent: (onError?: (error: unknown) => void) => void
}

export function useMilestoneCelebrationQueue(): MilestoneCelebrationQueue {
  const [queue, setQueue] = useState<QueuedMilestone[]>([])

  const checkGoal = useCallback(
    async (goalId: number | null | undefined, category: GoalCategory) => {
      if (goalId == null) {
        return
      }
      const pending = await listPendingCelebrations(goalId)
      if (pending.length === 0) {
        return
      }
      setQueue((current) => {
        const existingIds = new Set(current.map((item) => item.achievement.id))
        const additions = pending
          .filter((achievement) => !existingIds.has(achievement.id))
          .map((achievement) => ({ achievement, category }))
        return additions.length === 0 ? current : [...current, ...additions]
      })
    },
    [],
  )

  const dismissCurrent = useCallback((onError?: (error: unknown) => void) => {
    setQueue((current) => {
      const [first, ...rest] = current
      if (first) {
        celebrateMilestone(first.achievement.goal_id, first.achievement.id).catch((error) =>
          onError?.(error),
        )
      }
      return rest
    })
  }, [])

  return { current: queue[0], checkGoal, dismissCurrent }
}
