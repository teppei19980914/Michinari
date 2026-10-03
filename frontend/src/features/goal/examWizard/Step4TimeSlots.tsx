import { t } from '../../../locales/t'
import { Input } from '../../../components/Input'
import type { SlotAllocationRead } from '../../../api/goals'
import { SlotAllocationTable } from '../SlotAllocationTable'
import { totalMinutes, type SlotAllocationFormValues } from '../slotAllocationForm'
import { resolveWeekdaySlotTimes, resolveWeekendSlotTimes } from './simpleTimeSlots'

function SimpleTimeInputs({
  weekdayHours,
  weekendHours,
  onChangeWeekdayHours,
  onChangeWeekendHours,
}: {
  weekdayHours: string
  weekendHours: string
  onChangeWeekdayHours: (value: string) => void
  onChangeWeekendHours: (value: string) => void
}) {
  const weekdayTimes = resolveWeekdaySlotTimes(Number(weekdayHours) || 0)
  const weekendTimes = resolveWeekendSlotTimes(Number(weekendHours) || 0)

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-gray-600">{t('goals.examWizard.step4.description')}</p>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.examWizard.step4.weekdayHoursLabel')}
          <Input
            type="number"
            min={0}
            max={12}
            value={weekdayHours}
            onChange={(e) => onChangeWeekdayHours(e.target.value)}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('goals.examWizard.step4.weekendHoursLabel')}
          <Input
            type="number"
            min={0}
            max={12}
            value={weekendHours}
            onChange={(e) => onChangeWeekendHours(e.target.value)}
          />
        </label>
      </div>
      {Number(weekdayHours) > 0 && (
        <p className="text-xs text-gray-500">
          {t('goals.examWizard.step4.weekdayPreview', {
            start: weekdayTimes.startTime,
            end: weekdayTimes.endTime,
          })}
        </p>
      )}
      {Number(weekendHours) > 0 && (
        <p className="text-xs text-gray-500">
          {t('goals.examWizard.step4.weekendPreview', {
            start: weekendTimes.startTime,
            end: weekendTimes.endTime,
          })}
        </p>
      )}
      <p className="text-xs text-amber-700">{t('goals.examWizard.step4.timeDisclaimer')}</p>
      <p className="text-xs text-gray-500">{t('goals.examWizard.step4.laterNotice')}</p>
    </div>
  )
}

/** ウィザードStep4（学習時間を設定する。仕様書「資格モードの作成ウィザード」）。
 * スロットが1件も無い場合は平日/休日の簡易入力（`SimpleTimeInputs`）、既に存在する場合は
 * 既存スロットへの配分入力（`SlotAllocationTable`の再利用。仕様書「簡易時間設定からスロット
 * への変換」の「既にスロットが存在する場合は、ステップ4を省略する」を「簡易入力は省略し、
 * 配分入力を表示する」と解釈した設計）を表示する。配分の保持・保存はページ側が担う。 */
export function Step4TimeSlots({
  rows,
  values,
  onChangeMinutes,
  weekdayHours,
  weekendHours,
  onChangeWeekdayHours,
  onChangeWeekendHours,
}: {
  rows: SlotAllocationRead[]
  values: SlotAllocationFormValues
  onChangeMinutes: (slotId: number, minutes: string) => void
  weekdayHours: string
  weekendHours: string
  onChangeWeekdayHours: (value: string) => void
  onChangeWeekendHours: (value: string) => void
}) {
  if (rows.length === 0) {
    return (
      <SimpleTimeInputs
        weekdayHours={weekdayHours}
        weekendHours={weekendHours}
        onChangeWeekdayHours={onChangeWeekdayHours}
        onChangeWeekendHours={onChangeWeekendHours}
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-gray-600">{t('goals.examWizard.step4.existingSlotsDescription')}</p>
      <SlotAllocationTable rows={rows} values={values} readOnly={false} onChangeMinutes={onChangeMinutes} />
      <p className="text-sm text-gray-700">
        {t('goals.resourceAllocation.totalLabel')}: {totalMinutes(values)}
        {t('common.unit.minutes')}
      </p>
    </div>
  )
}
