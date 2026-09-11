import type { GoalCategory } from '../api/goals'

/**
 * 目標種別の全列挙（データ構造編 GoalCategory）。
 *
 * 画面の選択肢と「全種別を網羅する」テストの双方がここを参照する。各所で配列を書き写すと、
 * 種別を追加したときにテストだけ網羅から漏れ、網羅テストが意味を失う。
 */
export const GOAL_CATEGORIES: readonly GoalCategory[] = ['EXAM', 'READING', 'WORK'] as const
