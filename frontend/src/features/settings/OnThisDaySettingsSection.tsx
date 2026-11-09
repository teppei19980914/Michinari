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
  buildOnThisDaySettingsPayload,
  resolveOnThisDaySettingsGuard,
  type OnThisDaySettingsDraft,
} from './onThisDaySettings'

/** 1年前の今日（開発Todo_1年前の今日_v1.0 §0 V13）の設定。表示を止める、候補（何か月前か）、
 * 表示確率、記録本文の抜粋文字数を画面から変更できる（仕様書6.11「全ての設定項目は
 * 画面上から変更可能」）。 */
export function OnThisDaySettingsSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [draft, setDraft] = useState<OnThisDaySettingsDraft>({
    enabled: settings.on_this_day.enabled,
    candidateMonthsAgo: settings.on_this_day.candidate_months_ago,
    showProbability: settings.on_this_day.show_probability,
    bodyPreviewChars: settings.on_this_day.body_preview_chars,
  })

  const guard = resolveOnThisDaySettingsGuard(draft)

  const mutation = useMutation({
    mutationFn: () => updateSettings({ on_this_day: buildOnThisDaySettingsPayload(draft) }),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-text-primary">{t('settings.onThisDay.title')}</h2>
      <p className="text-sm text-text-faint">{t('settings.onThisDay.description')}</p>

      <label className="flex items-center gap-2 text-sm text-text-secondary">
        <input
          type="checkbox"
          checked={draft.enabled}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
        />
        {t('settings.onThisDay.enabledLabel')}
      </label>

      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('settings.onThisDay.candidateMonthsAgoLabel')}
        <Input
          type="text"
          value={draft.candidateMonthsAgo}
          disabled={!draft.enabled}
          onChange={(e) => setDraft({ ...draft, candidateMonthsAgo: e.target.value })}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('settings.onThisDay.showProbabilityLabel')}
        <Input
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={draft.showProbability}
          disabled={!draft.enabled}
          onChange={(e) => setDraft({ ...draft, showProbability: Number(e.target.value) })}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('settings.onThisDay.bodyPreviewCharsLabel')}
        <Input
          type="number"
          min={1}
          value={draft.bodyPreviewChars}
          disabled={!draft.enabled}
          onChange={(e) => setDraft({ ...draft, bodyPreviewChars: Number(e.target.value) })}
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
