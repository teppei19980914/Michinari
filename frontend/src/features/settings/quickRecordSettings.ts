/**
 * ひとこと記録モード（開発Todo「ひとこと記録」v1.0）の設定（SC-11）の入力判定。
 *
 * `last_mode_*`・`voice_hint_dismissed`は設定画面に出さない内部状態のため、ここでは
 * 画面から変更可能な`note_max_chars`のみを扱う（CODING_RULES.md「フロントの分岐は.tsへ」）。
 */

import type { AppSettingsUpdate } from '../../api/settings'

export type QuickRecordSettingsGuard = {
  canSubmit: boolean
  errorKey: string | null
}

export type QuickRecordSettingsDraft = {
  noteMaxChars: number
}

export function resolveQuickRecordSettingsGuard(
  draft: QuickRecordSettingsDraft,
): QuickRecordSettingsGuard {
  if (!Number.isInteger(draft.noteMaxChars) || draft.noteMaxChars < 1) {
    return { canSubmit: false, errorKey: 'settings.quickRecord.noteMaxCharsInvalid' }
  }
  return { canSubmit: true, errorKey: null }
}

export function buildQuickRecordSettingsPayload(
  draft: QuickRecordSettingsDraft,
): NonNullable<AppSettingsUpdate['quick_record']> {
  return { note_max_chars: draft.noteMaxChars }
}
