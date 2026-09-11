/**
 * 目標種別ごとに内容が変わる値（主にロケールキー）を、種別から1つ選ぶ。
 *
 * 資格試験・読書・仕事は同じ画面を共有しながら文言だけが異なる箇所が多い。各所で
 * 入れ子三項や接尾辞の組み立てを書くと、種別を追加したときに静かに既定（資格試験）へ
 * 落ちて「読書目標なのに科目の話が出る」類の不具合になる。実際に読書目標のクローズ確認と
 * 完全削除モーダルで発生した（2026-09-11）。
 *
 * `Record<GoalCategory, T>` を必須にすることで、種別の追加漏れを tsc が検知する。値は
 * 各呼び出し側に literal で書き並べるため、ロケールキーは grep で追跡できる。
 */
import type { GoalCategory } from '../../api/goals'

/**
 * @param category 目標種別
 * @param variants 種別ごとの値（全種別を必ず列挙する）
 * @returns `category` に対応する値
 *
 * @example
 * resolveByGoalCategory(goal.category, {
 *   EXAM: 'goals.basicInfo.nameLabel',
 *   READING: 'goals.basicInfo.nameLabelReading',
 *   WORK: 'goals.basicInfo.nameLabelWork',
 * })
 */
export function resolveByGoalCategory<T>(
  category: GoalCategory,
  variants: Record<GoalCategory, T>,
): T {
  return variants[category]
}
