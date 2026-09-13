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
