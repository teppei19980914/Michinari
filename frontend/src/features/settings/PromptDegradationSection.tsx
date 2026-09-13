import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { updateSettings, type AppSettingsRead } from '../../api/settings'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** プロンプト縮退設定（仕様書6.11「入力上限」「週次要約の注入週数」）。 */
export function PromptDegradationSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [maxPromptChars, setMaxPromptChars] = useState(
    String(settings.prompt_degradation.max_prompt_chars),
  )
  const [summaryInjectWeeks, setSummaryInjectWeeks] = useState(
    String(settings.prompt_degradation.summary_inject_weeks),
  )

  const mutation = useMutation({
    mutationFn: () =>
      updateSettings({
        prompt_degradation: {
          max_prompt_chars: Number(maxPromptChars),
          summary_inject_weeks: Number(summaryInjectWeeks),
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
      <h2 className="font-medium text-gray-900">{t('settings.promptDegradation.title')}</h2>
      <div className="flex gap-3">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.promptDegradation.maxPromptCharsLabel')}
          <Input
            type="number"
            min={1000}
            value={maxPromptChars}
            onChange={(e) => setMaxPromptChars(e.target.value)}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.promptDegradation.summaryInjectWeeksLabel')}
          <Input
            type="number"
            min={1}
            value={summaryInjectWeeks}
            onChange={(e) => setSummaryInjectWeeks(e.target.value)}
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
