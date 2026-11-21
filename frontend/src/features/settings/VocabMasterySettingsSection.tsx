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
  buildVocabMasterySettingsPayload,
  resolveVocabMasterySettingsGuard,
  type VocabMasterySettingsDraft,
} from './vocabMasterySettings'

/** 単語帳の習得の可視化（開発Todo_単語帳_v1.0 要件E E-U8）の設定。 */
export function VocabMasterySettingsSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [draft, setDraft] = useState<VocabMasterySettingsDraft>({
    masteryStreak: settings.vocab_mastery.mastery_streak,
    masteredTermsThresholds: settings.vocab_mastery.mastered_terms_thresholds,
  })

  const guard = resolveVocabMasterySettingsGuard(draft)

  const mutation = useMutation({
    mutationFn: () => updateSettings({ vocab_mastery: buildVocabMasterySettingsPayload(draft) }),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-text-primary">{t('settings.vocabMastery.title')}</h2>
      <p className="text-sm text-text-faint">{t('settings.vocabMastery.description')}</p>

      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('settings.vocabMastery.masteryStreakLabel')}
        <Input
          type="number"
          min={1}
          value={draft.masteryStreak}
          onChange={(e) => setDraft({ ...draft, masteryStreak: Number(e.target.value) })}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('settings.vocabMastery.masteredTermsThresholdsLabel')}
        <Input
          type="text"
          value={draft.masteredTermsThresholds}
          onChange={(e) => setDraft({ ...draft, masteredTermsThresholds: e.target.value })}
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
