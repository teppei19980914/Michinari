/**
 * 完全削除確認モーダル（MD-08、仕様書7.1.1）の文言キーを目標種別ごとに持つ。
 *
 * 削除の道連れ対象は種別ごとに異なる（データ構造編4.2、goal_service.delete_archived_goal）。
 * 資格試験は教材・学習実績、読書は書籍・想起記録、仕事は案件情報・業務記録である。
 * 種別を問わず資格試験向けの文言を出すと「何が消えるのか」を誤って伝えることになるため、
 * 取り消せない操作の説明として必ず分岐させる。
 */
import type { GoalCategory } from '../../api/goals'
import { resolveByGoalCategory } from './goalCategoryVariant'

/** 完全削除モーダルが使うロケールキーの組。 */
export type DeleteGoalLabelKeys = {
  /** 何が削除されるかの警告文。 */
  warningKey: string
  /** 実績も含めて削除するかのチェックボックス文言。 */
  cascadeCheckboxKey: string
  /** チェックを外した場合の挙動の補足。 */
  cascadeHintKey: string
}

//: 種別→キーの対応表。接尾辞を組み立てず全キーを literal で書くのは、キー改名時に grep で
//: 追跡できるようにするため。Record を使うことで、種別追加時の記述漏れを tsc が検知する。
const LABEL_KEYS: Record<GoalCategory, DeleteGoalLabelKeys> = {
  EXAM: {
    warningKey: 'goals.list.deleteModal.warning',
    cascadeCheckboxKey: 'goals.list.deleteModal.cascadeCheckbox',
    cascadeHintKey: 'goals.list.deleteModal.cascadeHint',
  },
  READING: {
    warningKey: 'goals.list.deleteModal.warningReading',
    cascadeCheckboxKey: 'goals.list.deleteModal.cascadeCheckboxReading',
    cascadeHintKey: 'goals.list.deleteModal.cascadeHintReading',
  },
  WORK: {
    warningKey: 'goals.list.deleteModal.warningWork',
    cascadeCheckboxKey: 'goals.list.deleteModal.cascadeCheckboxWork',
    cascadeHintKey: 'goals.list.deleteModal.cascadeHintWork',
  },
}

/**
 * 目標種別に対応する文言キーの組を返す。
 *
 * @param category 目標種別
 * @returns 警告文・チェックボックス・補足の各ロケールキー
 *
 * @example
 * resolveDeleteGoalLabelKeys('READING').warningKey
 * // => 'goals.list.deleteModal.warningReading'
 */
export function resolveDeleteGoalLabelKeys(category: GoalCategory): DeleteGoalLabelKeys {
  return resolveByGoalCategory(category, LABEL_KEYS)
}
