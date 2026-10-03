/** 受験結果フォーム（ExamResultPage.tsx）の選択肢。
 *
 * コンポーネントと同じファイルに置くと Fast Refresh が効かなくなるため
 * （oxlint react/only-export-components）、値だけをこのファイルへ分ける。
 * 型と配列の関係は materialOptions.ts と同じ方針。 */
import type { components } from '../../types/api.d.ts'

export type ExamResultType = components['schemas']['ExamResultType']

/** 受験結果の区分。既定は「結果待ち」（PENDING）。 */
export const RESULT_TYPES = ['PASS', 'FAIL', 'PENDING'] as const satisfies readonly ExamResultType[]
