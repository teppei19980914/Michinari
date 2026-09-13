/** 時間スロットのフォーム（SlotList.tsx の SlotForm）の入力欄。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた SlotForm から、
 * 入力欄の並びを切り出したものである。入力値の保持と送信内容の判定（新規作成では
 * 有効/無効を送らない）は呼び出し元に残す。 */
import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { SLOT_ENVIRONMENTS, WEEKDAYS, type SlotEnvironment } from './slotOptions'

/** 時間帯と環境（1行に並べる）。 */
export function SlotTimeFields({
  startTime,
  onChangeStartTime,
  endTime,
  onChangeEndTime,
  environment,
  onChangeEnvironment,
}: {
  startTime: string
  onChangeStartTime: (value: string) => void
  endTime: string
  onChangeEndTime: (value: string) => void
  environment: SlotEnvironment
  onChangeEnvironment: (value: SlotEnvironment) => void
}) {
  return (
    <div className="flex gap-2">
      <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
        {t('resources.slots.startTimeLabel')}
        <Input
          type="time"
          value={startTime}
          onChange={(e) => onChangeStartTime(e.target.value)}
          required
        />
      </label>
      <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
        {t('resources.slots.endTimeLabel')}
        <Input
          type="time"
          value={endTime}
          onChange={(e) => onChangeEndTime(e.target.value)}
          required
        />
      </label>
      <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
        {t('resources.slots.environmentLabel')}
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={environment}
          onChange={(e) => onChangeEnvironment(e.target.value as SlotEnvironment)}
        >
          {SLOT_ENVIRONMENTS.map((value) => (
            <option key={value} value={value}>
              {t(`goals.materials.environment.${value}`)}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}

/** 曜日の選択（1つ以上選ばないと保存できない）。 */
export function SlotWeekdaysField({
  weekdays,
  onToggle,
}: {
  weekdays: number[]
  onToggle: (weekday: number) => void
}) {
  return (
    <fieldset className="flex flex-col gap-1 text-sm text-gray-700">
      <legend>{t('resources.slots.weekdaysLabel')}</legend>
      <div className="flex flex-wrap gap-3">
        {WEEKDAYS.map((weekday) => (
          <label key={weekday} className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={weekdays.includes(weekday)}
              onChange={() => onToggle(weekday)}
            />
            {t(`resources.weekdays.${weekday}`)}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
