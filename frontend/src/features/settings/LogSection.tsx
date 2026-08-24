import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { updateSettings, type AppSettingsRead } from '../../api/settings'

/** ログ設定（仕様書6.11「AI通信ログの保存」「ログ保持期間」）。 */
export function LogSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [aiEnabled, setAiEnabled] = useState(settings.log.ai_enabled)
  const [retentionDays, setRetentionDays] = useState(String(settings.log.retention_days))

  const mutation = useMutation({
    mutationFn: () =>
      updateSettings({
        log: { ai_enabled: aiEnabled, retention_days: Number(retentionDays) },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('settings.log.title')}</h2>
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={aiEnabled}
          onChange={(e) => setAiEnabled(e.target.checked)}
        />
        {t('settings.log.aiEnabledLabel')}
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('settings.log.retentionDaysLabel')}
        <Input
          type="number"
          min={1}
          value={retentionDays}
          onChange={(e) => setRetentionDays(e.target.value)}
        />
      </label>
      <div className="flex justify-end">
        <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}
