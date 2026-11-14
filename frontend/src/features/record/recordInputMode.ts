/**
 * ひとこと記録モードの入力方式（開発Todo「ひとこと記録」v1.0 決定事項Q3）。
 * バックエンドの`RecordInputMode`（NORMAL/QUICK）と文字列を揃える。
 */

export type RecordInputMode = 'NORMAL' | 'QUICK'

/** `quick_record.last_mode_*`（app_setting、文字列）から初期表示モードを決める。
 * 想定外の値（初期導入直後の空文字列等）はNORMALへ落とす。 */
export function resolveInitialRecordInputMode(lastMode: string): RecordInputMode {
  return lastMode === 'QUICK' ? 'QUICK' : 'NORMAL'
}
