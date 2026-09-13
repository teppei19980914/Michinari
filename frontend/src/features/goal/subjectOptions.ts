/** 試験科目フォーム（SubjectsTab.tsx）の選択肢。
 *
 * コンポーネントと同じファイルに置くと Fast Refresh が効かなくなるため
 * （oxlint react/only-export-components）、値だけをこのファイルへ分ける。
 * 型と配列の関係は materialOptions.ts と同じ方針。 */
import type { components } from '../../types/api.d.ts'
import type { PassingScoreType } from './passingScore'

export type ExamDateType = components['schemas']['ExamDateType']

/** 受験日の指定方法（期間 / 確定日）。 */
export const EXAM_DATE_TYPES = ['RANGE', 'FIXED'] as const satisfies readonly ExamDateType[]
/** 合格基準の表し方（割合 / 素点）。 */
export const PASSING_SCORE_TYPES = [
  'PERCENTAGE',
  'RAW_SCORE',
] as const satisfies readonly PassingScoreType[]
