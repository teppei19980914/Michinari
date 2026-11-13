import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getSettings } from '../../api/settings'
import { QUERY_KEYS } from '../../constants/queryKeys'
import type { QuickRecordLastModes } from './useDailyReportDraft'

export type QuickRecordSettings = {
  /** カテゴリ別の初期表示モード（`quick_record.last_mode_*`）。設定取得前はundefined。 */
  lastModes: QuickRecordLastModes | undefined
  /** 1行メモの最大文字数（`quick_record.note_max_chars`）。設定取得前は既定値100。 */
  quickNoteMaxChars: number
}

/** ひとこと記録モード（開発Todo「ひとこと記録」v1.0）の設定値を取得する。
 * `DailyReportPage`本体の1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）
 * のために切り出した。lastModesはuseMemoで値が変わらない限り同一参照に保ち、
 * useDailyReportDraft内の一度きりの初期化エフェクトが毎レンダー再実行されないようにする。 */
export function useQuickRecordSettings(): QuickRecordSettings {
  const settingsQuery = useQuery({ queryKey: QUERY_KEYS.settings(), queryFn: getSettings })
  const quickRecordSettings = settingsQuery.data?.quick_record
  const lastModes = useMemo(
    () =>
      quickRecordSettings
        ? {
            exam: quickRecordSettings.last_mode_exam,
            reading: quickRecordSettings.last_mode_reading,
            work: quickRecordSettings.last_mode_work,
          }
        : undefined,
    [quickRecordSettings],
  )
  return { lastModes, quickNoteMaxChars: quickRecordSettings?.note_max_chars ?? 100 }
}
