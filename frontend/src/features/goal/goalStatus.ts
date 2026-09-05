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
 */
export function resolveGoalListTarget(goalId: number, status: GoalStatus): string {
  return isClosedGoalStatus(status) ? ROUTES.goalExport(goalId) : ROUTES.goalDetail(goalId)
}

/**
 * アーカイブ可能（進行中でない、かつ未アーカイブ）かどうかを判定する（仕様書6.15「アーカイブ
 * 操作が可能なのはACTIVE以外（下書き・一時停止・クローズ済み）の目標」）。
 */
export function canArchiveGoal(status: GoalStatus, archivedAt: string | null): boolean {
  return status !== 'ACTIVE' && archivedAt === null
}
