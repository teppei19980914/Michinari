import { ROUTES } from '../../constants/routes'
import type { components } from '../../types/api.d.ts'

type GoalStatus = components['schemas']['GoalStatus']

const CLOSED_STATUSES = new Set<GoalStatus>(['CLOSED_WITH_RESULT', 'CLOSED_WITHOUT_RESULT'])

/**
 * 目標がクローズ済み（読み取り専用）かどうかを判定する（仕様書6.2「クローズの場合、
 * 全項目を読み取り専用とする」）。GoalsListPage・GoalDetailPageで共用する
 * （CLAUDE.md DRYの原則）。
 */
export function isClosedGoalStatus(status: GoalStatus): boolean {
  return CLOSED_STATUSES.has(status)
}

/**
 * 目標一覧からの遷移先を判定する（仕様書5.2「クローズ済目標選択→SC-13」「目標選択→SC-03」）。
 * SC-13（ナレッジエクスポート）はPhase10で実装するため、クローズ済みの間は
 * 準備中プレースホルダー（goalExport）へ遷移する。
 */
export function resolveGoalListTarget(goalId: number, status: GoalStatus): string {
  return isClosedGoalStatus(status) ? ROUTES.goalExport(goalId) : ROUTES.goalDetail(goalId)
}
