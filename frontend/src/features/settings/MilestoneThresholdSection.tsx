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
  buildMilestoneThresholdSettingsPayload,
  resolveMilestoneThresholdGuard,
  type MilestoneThresholdFields,
} from './milestoneThresholdSettings'

const FIELD_LABEL_KEYS: Record<keyof MilestoneThresholdFields, string> = {
  consecutiveDaysThresholds: 'settings.milestoneThreshold.consecutiveDaysThresholdsLabel',
  totalRecordDaysThresholds: 'settings.milestoneThreshold.totalRecordDaysThresholdsLabel',
  readingTotalPagesThresholds: 'settings.milestoneThreshold.readingTotalPagesThresholdsLabel',
  readingCompletedBooksThresholds:
    'settings.milestoneThreshold.readingCompletedBooksThresholdsLabel',
  examOverallProgressThresholds: 'settings.milestoneThreshold.examOverallProgressThresholdsLabel',
  workRecordCountThresholds: 'settings.milestoneThreshold.workRecordCountThresholdsLabel',
}

const FIELD_ORDER: (keyof MilestoneThresholdFields)[] = [
  'consecutiveDaysThresholds',
  'totalRecordDaysThresholds',
  'readingTotalPagesThresholds',
  'readingCompletedBooksThresholds',
  'examOverallProgressThresholds',
  'workRecordCountThresholds',
]

/** 節目のお祝い（開発Todo_節目のお祝い_v1.0）の閾値設定。全角閾値はカンマ区切りの文字列
 * として編集する（仕様書6.11「全ての設定項目は画面上から変更可能」）。 */
export function MilestoneThresholdSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [fields, setFields] = useState<MilestoneThresholdFields>({
    consecutiveDaysThresholds: settings.milestone_threshold.consecutive_days_thresholds,
    totalRecordDaysThresholds: settings.milestone_threshold.total_record_days_thresholds,
    readingTotalPagesThresholds: settings.milestone_threshold.reading_total_pages_thresholds,
    readingCompletedBooksThresholds:
      settings.milestone_threshold.reading_completed_books_thresholds,
    examOverallProgressThresholds: settings.milestone_threshold.exam_overall_progress_thresholds,
    workRecordCountThresholds: settings.milestone_threshold.work_record_count_thresholds,
  })

  const guard = resolveMilestoneThresholdGuard(fields)

  const mutation = useMutation({
    mutationFn: () =>
      updateSettings({ milestone_threshold: buildMilestoneThresholdSettingsPayload(fields) }),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-text-primary">{t('settings.milestoneThreshold.title')}</h2>
      <p className="text-sm text-text-faint">{t('settings.milestoneThreshold.description')}</p>
      {FIELD_ORDER.map((field) => (
        <label key={field} className="flex flex-col gap-1 text-sm text-text-secondary">
          {t(FIELD_LABEL_KEYS[field])}
          <Input
            type="text"
            value={fields[field]}
            onChange={(e) => setFields({ ...fields, [field]: e.target.value })}
          />
        </label>
      ))}
      {guard.errorKey !== null && <p className="text-sm text-danger-text">{t(guard.errorKey)}</p>}
      <div className="flex justify-end">
        <Button disabled={mutation.isPending || !guard.canSubmit} onClick={() => mutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}
