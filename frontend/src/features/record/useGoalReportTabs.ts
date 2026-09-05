import { useState } from 'react'
import type { GoalRead } from '../../api/goals'

export type GoalReportTabs = {
  reportableGoals: GoalRead[]
  showGoalSelector: boolean
  selectedGoalId: number | null
  setSelectedGoalId: (goalId: number) => void
  selectedGoal: GoalRead | undefined
}

/** 着手中の目標が複数ある場合に、日次報告関連画面（SC-06/SC-08）の対象を目標単位のタブで
 * 切り替えるための状態をまとめる（DailyReportPage・DailyReportViewPage共通、CLAUDE.md
 * DRYの原則）。0〜1件のときは切替の必要がないため、showGoalSelector=falseとして呼び出し側が
 * 従来通り全項目を表示する。selectedGoalIdの初期化（最初のACTIVE目標を選択する等）は
 * 呼び出し側のデータ取得完了タイミングに依存するため、setSelectedGoalIdを呼び出し側の
 * 初期化ロジックへ委ねる。 */
export function useGoalReportTabs(goals: GoalRead[]): GoalReportTabs {
  const [selectedGoalId, setSelectedGoalId] = useState<number | null>(null)
  const reportableGoals = goals.filter((goal) => goal.status === 'ACTIVE')
  const showGoalSelector = reportableGoals.length > 1
  const selectedGoal = showGoalSelector
    ? reportableGoals.find((goal) => goal.id === selectedGoalId)
    : undefined

  return { reportableGoals, showGoalSelector, selectedGoalId, setSelectedGoalId, selectedGoal }
}
