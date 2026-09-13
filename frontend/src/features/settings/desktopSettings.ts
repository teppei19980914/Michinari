/**
 * デスクトップ・通知設定（SC-11）の入力判定。
 *
 * CODING_RULES.md「フロントの分岐は `.ts` へ切り出す」に従い、判定を純粋関数として
 * ここに置き、コンポーネント（DesktopSection.tsx）は描画と通信に専念させる。
 *
 * 通知時刻の形式は、バックエンドの
 * `app/services/notification_service.py: NOTIFICATION_TIME_PATTERN` と同じ規則である
 * （`HH:MM` の24時間表記）。言語が違うため機械的に共有できないが、片方だけ緩めると
 * 画面で保存できてもサーバが弾く（またはその逆）という食い違いになる。
 */

/** 通知時刻の入力形式（`00:00` 〜 `23:59`）。`<input type="time">` の出力と一致させる。 */
export const NOTIFICATION_TIME_PATTERN = /^([01]\d|2[0-3]):([0-5]\d)$/

/** 保存操作の可否と、不可の場合に表示する文言のロケールキー。 */
export type DesktopSettingsGuard = {
  canSubmit: boolean
  errorKey: string | null
}

/** 画面で編集中のデスクトップ・通知設定。 */
export type DesktopSettingsDraft = {
  openBrowserOnStartup: boolean
  launchAtLogin: boolean
  notificationEnabled: boolean
  notificationTime: string
}

/** サーバへ送る `desktop` グループの内容（`AppSettingsUpdate['desktop']` と同じ形）。 */
export type DesktopSettingsPayload = {
  open_browser_on_startup: boolean
  launch_at_login: boolean
  notification_enabled: boolean
  notification_time?: string
}

/**
 * 通知時刻の文字列が受け付けられる形式かを判定する。
 *
 * @param value `<input type="time">` が返す文字列。
 * @returns 形式が正しければ true。
 *
 * @example
 * isValidNotificationTime('21:00') // => true
 * isValidNotificationTime('24:00') // => false
 */
export function isValidNotificationTime(value: string): boolean {
  return NOTIFICATION_TIME_PATTERN.test(value)
}

/**
 * デスクトップ・通知設定を保存してよいかを判定する。
 *
 * 通知を無効にしている場合は時刻を見ない。ブラウザが空文字を返す状況（時刻欄をクリアした
 * 場合）でも、通知を使わない利用者の保存を妨げないためである。
 *
 * @param notificationEnabled 通知を有効にするか。
 * @param notificationTime 通知時刻の入力値。
 * @returns 保存可否と、不可の場合の文言キー。
 *
 * @example
 * resolveDesktopSettingsGuard(true, '') // => { canSubmit: false, errorKey: '...' }
 * resolveDesktopSettingsGuard(false, '') // => { canSubmit: true, errorKey: null }
 */
export function resolveDesktopSettingsGuard(
  notificationEnabled: boolean,
  notificationTime: string,
): DesktopSettingsGuard {
  if (!notificationEnabled) {
    return { canSubmit: true, errorKey: null }
  }
  if (!isValidNotificationTime(notificationTime)) {
    return { canSubmit: false, errorKey: 'settings.desktop.notificationTimeInvalid' }
  }
  return { canSubmit: true, errorKey: null }
}

/**
 * サーバへ送る内容を組み立てる。
 *
 * **通知時刻は、形式が正しいときだけ送る。** 通知を無効にしている利用者は時刻欄を空に
 * できる（`resolveDesktopSettingsGuard` がそれを許す）が、空文字をそのまま送ると
 * サーバのスキーマ（`DesktopSettingsUpdate.notification_time` の `min_length=1`）が
 * 拒否し、保存ボタンは押せるのに必ず失敗する状態になる。送らなければ、保存済みの時刻が
 * そのまま保たれる（PATCHのため、指定しない項目は変更されない）。
 *
 * @param draft 画面で編集中の値。
 * @returns `updateSettings` へ渡す `desktop` グループの内容。
 *
 * @example
 * buildDesktopSettingsPayload({ ..., notificationEnabled: false, notificationTime: '' })
 * // => notification_time を含まない
 */
export function buildDesktopSettingsPayload(draft: DesktopSettingsDraft): DesktopSettingsPayload {
  const payload: DesktopSettingsPayload = {
    open_browser_on_startup: draft.openBrowserOnStartup,
    launch_at_login: draft.launchAtLogin,
    notification_enabled: draft.notificationEnabled,
  }
  if (isValidNotificationTime(draft.notificationTime)) {
    payload.notification_time = draft.notificationTime
  }
  return payload
}
