/** 実績入力欄（StudyLogFields.tsx）の1教材分のカード。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた StudyLogFields から、
 * 教材1件分の入力欄を切り出したものである。入力値の保持は呼び出し元（SC-06 日次報告 /
 * SC-07 進捗のみ登録の画面）に残し、ここは受け取った値を描画して変更を返すことに徹する。
 *
 * 品質指標の入力欄は方式によって3通り（非表示・0〜100の数値・5段階選択）に変わる。
 * 取り違えても「何かの入力欄が並んでいる」状態になり画面では気づけないため、
 * 方式の判定は qualityInput.ts に置き、ここはその結果で描き分けるだけにする。 */
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

export function StudyLogCard({
  item,
  value,
  slotNames,
  onChangeField,
  onChangeSlotMinutes,
}: {
  item: QuotaItemRead
  value: StudyLogFormValue
  slotNames: Map<number, string>
  onChangeField: (materialId: number, field: keyof StudyLogFormValue, value: string) => void
  onChangeSlotMinutes: (materialId: number, slotMinutes: SlotMinutesFormValue) => void
}) {
  const qualityKind = resolveQualityInputKind(item.quality_metric_type)

  return (
    <Card>
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
        label={t('dailyReport.studyLog.slotMinutesLabel')}
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
