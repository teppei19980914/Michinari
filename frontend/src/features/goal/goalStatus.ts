import { ROUTES } from '../../constants/routes'
import type { GoalCategory, GoalRead } from '../../api/goals'
import type { components } from '../../types/api.d.ts'

type GoalStatus = components['schemas']['GoalStatus']
type GoalOperation = components['schemas']['GoalOperation']

/** 完了・中断（読み取り専用）の状態（仕様書6.2「クローズの場合、全項目を読み取り専用とする」）。 */
const CLOSED_STATUSES = new Set<GoalStatus>(['CLOSED_WITH_RESULT', 'CLOSED_WITHOUT_RESULT'])

/** 目標一覧の既定表示に含める状態（開発Todo 1-9：下書き・実行中・一時停止）。 */
const DEFAULT_LISTED_STATUSES = new Set<GoalStatus>(['DRAFT', 'ACTIVE', 'PAUSED'])

/**
 * 目標がクローズ済み（読み取り専用）かどうかを判定する。GoalsListPage・GoalDetailPageで共用する
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
 * 状態の表示名のロケールキーを、目標種別ごとに返す（開発Todo 1-2）。内部の状態は共通で、
 * 表示名だけを種別で変える（読書の完了＝「読了」、仕事の中断＝「中止・打ち切り」）。
 * キーを種別と状態の組で全て列挙しておくことで、文言の漏れを ja.json の検証で検知できる。
 */
export function goalStatusLabelKey(category: GoalCategory, status: GoalStatus): string {
  return `goals.status.${category}.${status}`
}

/**
 * 総括レポート・読了レポートを生成できるか。完了（CLOSED_WITH_RESULT）の目標のみ（利用者方針
 * 2026-10-04。資格試験・読書で同じ扱い。サーバーの retrospective_service と揃える）。
 * 生成は出力画面の生成ボタンを押したときのみ行う。
 */
export function canGenerateRetrospective(status: GoalStatus): boolean {
  return status === 'CLOSED_WITH_RESULT'
}

/** 目標一覧の既定表示に含めるか（アーカイブ済みは「すべて表示」でのみ見える）。 */
export function isDefaultListedGoal(goal: Pick<GoalRead, 'status' | 'archived_at'>): boolean {
  return goal.archived_at === null && DEFAULT_LISTED_STATUSES.has(goal.status)
}

/**
 * 目標に対して、その操作が画面から実行できるかを判定する。操作の可否はサーバーが遷移表から
 * 算出して返す（available_operations）ため、画面は同じ判定を持たない（開発Todo 5-2）。
 */
export function hasOperation(
  goal: Pick<GoalRead, 'available_operations'>,
  operation: GoalOperation,
): boolean {
  return goal.available_operations.includes(operation)
}
