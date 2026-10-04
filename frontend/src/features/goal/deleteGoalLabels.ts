/**
 * 削除確認モーダル（開発Todo 1-4）の警告文のキーを目標種別ごとに持つ。
 *
 * 削除の道連れ対象は種別ごとに異なる（資格試験は教材・学習実績・評価、読書は書籍・想起記録、
 * 仕事は案件情報・業務記録・評価レポート）。種別を問わず資格試験向けの文言を出すと「何が消えるのか」
 * を誤って伝えることになるため、取り消せない操作の説明として必ず分岐させる。削除は常に関連データを
 * 含めて行うため（旧「実績も含めるかのチェック」は廃止）、警告文だけを種別ごとに持つ。
 */
import type { GoalCategory } from '../../api/goals'
import { resolveByGoalCategory } from './goalCategoryVariant'

//: 種別→警告文キーの対応表。キーは literal で書き、キー改名時に grep で追跡できるようにする。
const WARNING_KEYS: Record<GoalCategory, string> = {
  EXAM: 'goals.delete.warning.EXAM',
  READING: 'goals.delete.warning.READING',
  WORK: 'goals.delete.warning.WORK',
}

/**
 * 目標種別に対応する削除警告文のキーを返す。
 *
 * @example
 * resolveDeleteGoalWarningKey('READING') // => 'goals.delete.warning.READING'
 */
export function resolveDeleteGoalWarningKey(category: GoalCategory): string {
  return resolveByGoalCategory(category, WARNING_KEYS)
}
