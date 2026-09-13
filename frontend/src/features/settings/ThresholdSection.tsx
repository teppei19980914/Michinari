import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { updateSettings, type AppSettingsRead } from '../../api/settings'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 閾値設定（仕様書6.11「警告倍率」「強制リプラン超過日数」）。 */
export function ThresholdSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [warningRatioPercent, setWarningRatioPercent] = useState(
    String(Math.round(settings.threshold.warning_ratio * 100)),
  )
  const [replanOverrunDays, setReplanOverrunDays] = useState(
    String(settings.threshold.replan_overrun_days),
  )

  const mutation = useMutation({
    mutationFn: () =>
      updateSettings({
        threshold: {
          warning_ratio: Number(warningRatioPercent) / 100,
          replan_overrun_days: Number(replanOverrunDays),
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('settings.threshold.title')}</h2>
      <div className="flex gap-3">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.threshold.warningRatioLabel')}
          <Input
            type="number"
            min={101}
            value={warningRatioPercent}
            onChange={(e) => setWarningRatioPercent(e.target.value)}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.threshold.replanOverrunDaysLabel')}
          <Input
            type="number"
            min={1}
            value={replanOverrunDays}
            onChange={(e) => setReplanOverrunDays(e.target.value)}
          />
        </label>
      </div>
      <div className="flex justify-end">
        <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}
