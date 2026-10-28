import { isValidNotificationTime } from '../settings/desktopSettings'

/**
 * 記録リマインドの到達性案内（新規利用者向け1問案内・既存利用者向けダッシュボード案内、
 * 開発Todo リマインド導線）の判定ロジック。CODING_RULES.md「フロントの分岐は `.ts` へ
 * 切り出す」に従い、判定を純粋関数としてここに置く。
 */

export { isValidNotificationTime }

/** 自動起動の即時反映結果（`POST /desktop/autostart/sync`）。 */
export type AutostartSyncOutcome = {
  supported: boolean
  applied: boolean
}

/**
 * 自動起動の即時反映結果から、利用者へ表示する通知の種類と文言キーを決める。
 *
 * - `applied`: 反映に成功した（成功のトーストは表示側が既存の「保存しました」等で足りるため、
 *   このキーは呼び出し側で無視してよい）。
 * - `info`: 開発環境（`supported=false`）のため反映を試みていない。失敗ではない。
 * - `error`: 配布パッケージ上でレジストリへの反映に失敗した。
 *
 * @example
 * resolveAutostartSyncMessageKey({ supported: false, applied: false })
 * // => { kind: 'info', messageKey: 'desktop.autostartSync.unsupported' }
 */
export function resolveAutostartSyncMessageKey(
  outcome: AutostartSyncOutcome,
): { kind: 'applied' | 'info' | 'error'; messageKey: string | null } {
  if (outcome.applied) {
    return { kind: 'applied', messageKey: null }
  }
  if (!outcome.supported) {
    return { kind: 'info', messageKey: 'desktop.autostartSync.unsupported' }
  }
  return { kind: 'error', messageKey: 'desktop.autostartSync.failed' }
}
