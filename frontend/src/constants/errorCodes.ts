/**
 * 画面が分岐に使うAPIエラーコード（データ構造編6.3「エラーコード」）。
 *
 * 表示用の文言は `locales/ja.json` の `errors.<コード>` が持つ（ApiError.localizedMessage）。
 * ここに置くのは「コード上の名前」であり、画面ごとに文字列リテラルを直書きしないための
 * 集約先である（CODING_RULES.md 置き場所ルール）。
 */
export const ERROR_CODES = {
  /** 受験結果が未登録のままのクローズ要求。状態エラーではなく、確認さえ取れば実行できる。 */
  CLOSE_CONFIRMATION_REQUIRED: 'CLOSE_CONFIRMATION_REQUIRED',
  /** 許可されない状態遷移（クローズ済み目標への再クローズ等）。確認では解消しない。 */
  INVALID_STATE_TRANSITION: 'INVALID_STATE_TRANSITION',
  /** スロットへの配分時間の合計が、そのスロットの連続時間を超過（仕様書NT-04）。 */
  RESOURCE_EXCEEDED: 'RESOURCE_EXCEEDED',
} as const

/**
 * 削除不可エラー（コードは`VALIDATION_ERROR`のまま）の`error.details[].reason`に入る値
 * （app/services/exceptions.pyのreasonクラス属性、2026-09-19）。表示用文言は
 * `locales/ja.json`の`errors.reasons.<値>`が持つ（ApiError.localizedMessage）。
 */
export const ERROR_REASONS = {
  /** 実績（study_log）が残る教材の削除拒否。 */
  MATERIAL_HAS_LOGS: 'MATERIAL_HAS_LOGS',
  /** 想起記録（reading_log）が残る書籍の削除拒否。 */
  BOOK_HAS_LOGS: 'BOOK_HAS_LOGS',
  /** 業務記録（work_log）が残る案件情報の削除拒否。 */
  WORK_ASSIGNMENT_HAS_LOGS: 'WORK_ASSIGNMENT_HAS_LOGS',
} as const
