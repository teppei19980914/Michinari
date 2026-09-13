/** デスクトップ・通知設定の入力判定のテスト（Phase37）。
 *
 * 通知時刻の受け付ける形式は、バックエンドの
 * `app/services/notification_service.py: NOTIFICATION_TIME_PATTERN` と同じでなければ
 * ならない（画面で保存できてもサーバが弾く、という食い違いを防ぐ）。境界値を両側から
 * 押さえる。 */
import { describe, expect, it } from 'vitest'
import {
  buildDesktopSettingsPayload,
  isValidNotificationTime,
  resolveDesktopSettingsGuard,
} from './desktopSettings'

describe('isValidNotificationTime', () => {
  it.each(['00:00', '09:05', '21:00', '23:59'])('accepts %s', (value) => {
    expect(isValidNotificationTime(value)).toBe(true)
  })

  it.each([
    ['24:00', '時が範囲外'],
    ['23:60', '分が範囲外'],
    ['9:00', 'ゼロ埋めなし'],
    ['2100', '区切りなし'],
    ['', '空文字'],
    ['21:00:00', '秒付き'],
    ['夜9時', '日本語'],
  ])('rejects %s (%s)', (value) => {
    expect(isValidNotificationTime(value)).toBe(false)
  })
})

describe('resolveDesktopSettingsGuard', () => {
  it('allows saving when the notification time is valid', () => {
    expect(resolveDesktopSettingsGuard(true, '21:00')).toEqual({
      canSubmit: true,
      errorKey: null,
    })
  })

  it('blocks saving and explains why when the time is malformed', () => {
    const guard = resolveDesktopSettingsGuard(true, '25:00')

    expect(guard.canSubmit).toBe(false)
    expect(guard.errorKey).toBe('settings.desktop.notificationTimeInvalid')
  })

  it('ignores the time while notifications are disabled', () => {
    // 通知を使わない利用者が、時刻欄を空にしたせいで保存できなくなるのを防ぐ。
    expect(resolveDesktopSettingsGuard(false, '')).toEqual({ canSubmit: true, errorKey: null })
  })

  it('ignores a malformed time while notifications are disabled', () => {
    expect(resolveDesktopSettingsGuard(false, 'こわれた値')).toEqual({
      canSubmit: true,
      errorKey: null,
    })
  })
})

describe('buildDesktopSettingsPayload', () => {
  const draft = {
    openBrowserOnStartup: true,
    launchAtLogin: false,
    notificationEnabled: true,
    notificationTime: '21:00',
  }

  it('sends every field when the time is valid', () => {
    expect(buildDesktopSettingsPayload(draft)).toEqual({
      open_browser_on_startup: true,
      launch_at_login: false,
      notification_enabled: true,
      notification_time: '21:00',
    })
  })

  it('omits an empty time so the server does not reject the save', () => {
    // 空文字を送るとサーバのスキーマ（min_length=1）が400を返し、保存ボタンは押せるのに
    // 必ず失敗する状態になる。送らなければ保存済みの時刻がそのまま保たれる。
    const payload = buildDesktopSettingsPayload({
      ...draft,
      notificationEnabled: false,
      notificationTime: '',
    })

    expect(payload).toEqual({
      open_browser_on_startup: true,
      launch_at_login: false,
      notification_enabled: false,
    })
    expect('notification_time' in payload).toBe(false)
  })

  it('omits a malformed time for the same reason', () => {
    const payload = buildDesktopSettingsPayload({
      ...draft,
      notificationEnabled: false,
      notificationTime: '25:00',
    })

    expect('notification_time' in payload).toBe(false)
  })

  it('carries the toggled switches through', () => {
    const payload = buildDesktopSettingsPayload({
      ...draft,
      openBrowserOnStartup: false,
      launchAtLogin: true,
    })

    expect(payload.open_browser_on_startup).toBe(false)
    expect(payload.launch_at_login).toBe(true)
  })
})
