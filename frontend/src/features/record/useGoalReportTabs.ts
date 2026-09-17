import { useState } from 'react'
import type { GoalRead } from '../../api/goals'

export type GoalReportTabs = {
  reportableGoals: GoalRead[]
  showGoalSelector: boolean
  selectedGoalId: number | null
  setSelectedGoalId: (goalId: number) => void
  selectedGoal: GoalRead | undefined
}

/**
 * 着手中の目標が複数ある場合に、日次報告関連画面（SC-06/SC-08）の対象を目標単位のタブで
 * 切り替えるための状態をまとめる（DailyReportPage・DailyReportViewPage共通、CLAUDE.md
 * DRYの原則）。0〜1件のときは切替の必要がないため、showGoalSelector=falseとして呼び出し側が
 * 従来通り全項目を表示する。
 *
 * 初期表示タブ（最初のACTIVE目標）は、利用者が未選択（selectedGoalId===null）の間、
 * 取得済みのreportableGoalsから都度導出する（記録画面改善タスク2026-09-17。以前は
 * useEffect+setStateで取得完了後の1回だけ初期化していたが、描画中に導出できる値を
 * useEffectで扱うと余分な再レンダーが発生するため、導出値として計算する方式に変更した。
 * react/set-state-in-effect対応）。DailyReportPage/DailyReportViewPageの双方が同型の
 * 初期化を別々に持っていた重複もあわせて解消した（CODING_RULES.md①DRYの原則）。
 */
export function useGoalReportTabs(goals: GoalRead[]): GoalReportTabs {
  const [selectedGoalId, setSelectedGoalId] = useState<number | null>(null)
  const reportableGoals = goals.filter((goal) => goal.status === 'ACTIVE')
  const showGoalSelector = reportableGoals.length > 1
  const effectiveSelectedGoalId = selectedGoalId ?? reportableGoals[0]?.id ?? null
  const selectedGoal = showGoalSelector
    ? reportableGoals.find((goal) => goal.id === effectiveSelectedGoalId)
    : undefined

  return {
    reportableGoals,
    showGoalSelector,
    selectedGoalId: effectiveSelectedGoalId,
    setSelectedGoalId,
    selectedGoal,
  }
}
