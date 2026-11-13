import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { getSettings, updateSettings } from '../../api/settings'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 音声入力ヒント（Win+H案内）。日記欄・想起欄・業務内容欄・ひとこと欄の4箇所で共通の
 * 使い回しとする（開発Todo「ひとこと記録」v1.0 Q5・F6）。一度閉じると、サーバ側の
 * 既読フラグ（`quick_record.voice_hint_dismissed`）により以後どの欄でも表示しない
 * （localStorageではなくサーバ側の非表示app_settingへ保存する既存パターン、F3）。 */
export function VoiceInputHint() {
  const queryClient = useQueryClient()
  const settingsQuery = useQuery({ queryKey: QUERY_KEYS.settings(), queryFn: getSettings })
  const dismissMutation = useMutation({
    mutationFn: () => updateSettings({ quick_record: { voice_hint_dismissed: true } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() }),
  })

  if (!settingsQuery.data || settingsQuery.data.quick_record.voice_hint_dismissed) {
    return null
  }

  return (
    <p className="flex items-center justify-between gap-2 text-xs text-text-disabled">
      <span>{t('dailyReport.voiceInputHint')}</span>
      <button
        type="button"
        disabled={dismissMutation.isPending}
        onClick={() => dismissMutation.mutate()}
        aria-label={t('dailyReport.voiceInputHintDismiss')}
        className="shrink-0 hover:opacity-70 disabled:opacity-50"
      >
        ×
      </button>
    </p>
  )
}
