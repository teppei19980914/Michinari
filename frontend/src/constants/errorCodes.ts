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
