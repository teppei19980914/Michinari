/** 教材フォーム（MaterialsTab.tsx）の選択肢。
 *
 * コンポーネントと同じファイルに置くと Fast Refresh が効かなくなるため
 * （oxlint react/only-export-components）、値だけをこのファイルへ分ける。
 *
 * 型は自動生成（openapi-typescript）の定義から取り、配列は `satisfies` で各要素が
 * その型に収まることを検査する。列挙値を手書きで二重定義しないため
 * （CLAUDE.md「フロントエンドのAPI型の手書き」の禁止）。 */
import type { components } from '../../types/api.d.ts'

export type MaterialEnvironment = components['schemas']['Environment']
export type MaterialQualityMetricType = components['schemas']['QualityMetricType']

/** 教材の学習に必要な環境。`ANY` は「どこでもよい」。 */
export const ENVIRONMENTS = ['ANY', 'PC', 'MOBILE'] as const satisfies readonly MaterialEnvironment[]
/** 品質指標の方式（入力欄の形式が変わる。qualityInput.ts の判定と対応）。 */
export const QUALITY_METRIC_TYPES = [
  'NONE',
  'OBJECTIVE',
  'SELF_SCORED',
  'SUBJECTIVE',
] as const satisfies readonly MaterialQualityMetricType[]
