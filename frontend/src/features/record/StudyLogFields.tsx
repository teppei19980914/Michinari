import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import {
  resolveQualityInputKind,
  resolveQualityLabelKey,
  SUBJECTIVE_SCALE_OPTIONS,
} from './qualityInput'
import { SlotMinutesFields } from './SlotMinutesFields'
import type { SlotMinutesFormValue } from './slotMinutesForm'
import type { StudyLogFormValue } from './studyLogForm'
import type { QuotaItemRead } from '../../api/records'
import { groupByGoal } from '../../utils/groupByGoal'

type StudyLogFieldsProps = {
  quotaItems: QuotaItemRead[]
  values: Record<number, StudyLogFormValue>
  onChangeField: (materialId: number, field: keyof StudyLogFormValue, value: string) => void
  /** 時間枠ごとの投下時間の変更（仕様書6.5）。 */
  onChangeSlotMinutes: (materialId: number, slotMinutes: SlotMinutesFormValue) => void
  /** 追加候補の全時間枠（slot_id → 名称）。「他の時間枠を追加」で使う。 */
  slotNames: Map<number, string>
  /** SC-07専用: 投下時間が任意入力である旨を明示する（仕様書6.6）。 */
  showMinutesOptionalNotice?: boolean
}

/** 実績入力欄（教材別の投下時間・完了分量・周回・品質指標）。SC-06/SC-07で共有する
 * （仕様書6.5・6.6は同一の入力表を前提としており、CLAUDE.md DRYの原則に従い共通化する）。 */
export function StudyLogFields({
  quotaItems,
  values,
  onChangeField,
  onChangeSlotMinutes,
  slotNames,
  showMinutesOptionalNotice = false,
}: StudyLogFieldsProps) {
  if (quotaItems.length === 0) {
    return <p className="text-sm text-gray-500">{t('dailyReport.studyLog.empty')}</p>
  }

  const renderCard = (item: QuotaItemRead) => {
    const value = values[item.material_id]
    if (!value) {
      return null
    }
    const qualityKind = resolveQualityInputKind(item.quality_metric_type)
    return (
      <Card key={item.material_id}>
        <div className="flex items-center justify-between">
          <p className="font-medium text-gray-900">{item.material_name}</p>
          <p className="text-sm text-gray-500">
            {t('dailyReport.studyLog.cycleLabel', {
              current: item.current_cycle,
              planned: item.planned_cycles,
            })}
          </p>
        </div>
        <p className="mt-1 text-xs text-gray-500">
          {t('dailyReport.studyLog.quotaLabel', {
            quota: Math.round(item.daily_quota * 10) / 10,
            unit: item.unit_label,
          })}
        </p>
        <SlotMinutesFields
          defaults={item.slot_defaults}
          values={value.slotMinutes}
          addedSlotIds={Object.keys(value.slotMinutes).map(Number)}
          slotNames={slotNames}
          onChange={(slotId, minutes) =>
            onChangeSlotMinutes(item.material_id, { ...value.slotMinutes, [slotId]: minutes })
          }
          onAddSlot={(slotId) =>
            onChangeSlotMinutes(item.material_id, { ...value.slotMinutes, [slotId]: '' })
          }
        />
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs text-gray-600">
            {t('dailyReport.studyLog.amountLabel', { unit: item.unit_label })}
            <Input
              type="number"
              min={0}
              value={value.amountCompleted}
              onChange={(e) => onChangeField(item.material_id, 'amountCompleted', e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray-600">
            {t('dailyReport.studyLog.cycleNumberLabel')}
            <Input
              type="number"
              min={1}
              value={value.cycleNumber}
              onChange={(e) => onChangeField(item.material_id, 'cycleNumber', e.target.value)}
            />
          </label>
          {qualityKind !== 'HIDDEN' && (
            <label className="flex flex-col gap-1 text-xs text-gray-600">
              {t(resolveQualityLabelKey(item.quality_metric_type))}
              {qualityKind === 'PERCENT' ? (
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={value.qualityValue}
                  onChange={(e) => onChangeField(item.material_id, 'qualityValue', e.target.value)}
                />
              ) : (
                <select
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm"
                  value={value.qualityValue}
                  onChange={(e) => onChangeField(item.material_id, 'qualityValue', e.target.value)}
                >
                  <option value="">{t('dailyReport.studyLog.qualityUnselected')}</option>
                  {SUBJECTIVE_SCALE_OPTIONS.map((scale) => (
                    <option key={scale} value={scale}>
                      {t(`dailyReport.studyLog.subjectiveScale.${scale}`)}
                    </option>
                  ))}
                </select>
              )}
            </label>
          )}
        </div>
      </Card>
    )
  }

  const goalGroups = groupByGoal(quotaItems)

  return (
    <div className="flex flex-col gap-3">
      {goalGroups.map((group) => (
        <div key={group.goalId} className="flex flex-col gap-3">
          {goalGroups.length > 1 && (
            <h3 className="font-medium text-gray-900">{group.goalName}</h3>
          )}
          {group.items.map(renderCard)}
        </div>
      ))}
      {showMinutesOptionalNotice && (
        <p className="text-xs text-gray-500">{t('progressOnly.minutesOptionalNotice')}</p>
      )}
    </div>
  )
}
