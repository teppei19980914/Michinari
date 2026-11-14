import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import { updateSettings, type AppSettingsRead } from '../../api/settings'
import { QUERY_KEYS } from '../../constants/queryKeys'
import {
  buildQuickRecordSettingsPayload,
  resolveQuickRecordSettingsGuard,
  type QuickRecordSettingsDraft,
} from './quickRecordSettings'

/** ひとこと記録モード（開発Todo「ひとこと記録」v1.0）の設定。1行メモの最大文字数のみを
 * 画面から変更できる（最後に使ったモード・音声ヒント既読フラグは内部状態のため非表示）。 */
export function QuickRecordSettingsSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [draft, setDraft] = useState<QuickRecordSettingsDraft>({
    noteMaxChars: settings.quick_record.note_max_chars,
  })

  const guard = resolveQuickRecordSettingsGuard(draft)

  const mutation = useMutation({
    mutationFn: () => updateSettings({ quick_record: buildQuickRecordSettingsPayload(draft) }),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-text-primary">{t('settings.quickRecord.title')}</h2>
      <p className="text-sm text-text-faint">{t('settings.quickRecord.description')}</p>

      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('settings.quickRecord.noteMaxCharsLabel')}
        <Input
          type="number"
          min={1}
          value={draft.noteMaxChars}
          onChange={(e) => setDraft({ noteMaxChars: Number(e.target.value) })}
        />
      </label>

      {guard.errorKey !== null && <p className="text-sm text-danger-text">{t(guard.errorKey)}</p>}
      <div className="flex justify-end">
        <Button disabled={mutation.isPending || !guard.canSubmit} onClick={() => mutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}
