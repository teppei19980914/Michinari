import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { buildSlotRows, sumSlotMinutes, type SlotMinutesFormValue } from './slotMinutesForm'
import type { components } from '../../types/api.d.ts'

type SlotDefaultMinutesRead = components['schemas']['SlotDefaultMinutesRead']
type SlotMinutesRead = components['schemas']['SlotMinutesRead']

type SlotMinutesFieldsProps = {
  /** 配分の按分結果（入力欄の既定値かつ既定で並べる枠）。 */
  defaults: SlotDefaultMinutesRead[]
  /** 既存実績の内訳（再編集時に枠を並べるために使う）。 */
  existing?: SlotMinutesRead[]
  values: SlotMinutesFormValue
  /** 利用者が「他の時間枠を追加」で加えた枠のID。 */
  addedSlotIds: number[]
  /** 追加候補の全時間枠（slot_id → 名称）。 */
  slotNames: Map<number, string>
  onChange: (slotId: number, value: string) => void
  onAddSlot: (slotId: number) => void
}

/**
 * 時間枠ごとの投下時間の入力欄（仕様書6.5「時間枠ごとの投下時間の入力」）。
 * 資格試験の教材カードと読書の書籍カードで共用する（CLAUDE.md DRYの原則）。
 */
export function SlotMinutesFields({
  defaults,
  existing,
  values,
  addedSlotIds,
  slotNames,
  onChange,
  onAddSlot,
}: SlotMinutesFieldsProps) {
  const rows = buildSlotRows(defaults, existing, addedSlotIds, slotNames)
  const shownSlotIds = new Set(rows.map((row) => row.slotId))
  const addable = [...slotNames.entries()].filter(([slotId]) => !shownSlotIds.has(slotId))

  return (
    <div className="mt-2 flex flex-col gap-1">
      <p className="text-xs text-gray-600">{t('dailyReport.studyLog.slotMinutesLabel')}</p>
      {rows.length === 0 ? (
        <p className="text-xs text-gray-500">{t('dailyReport.studyLog.noAllocatedSlots')}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {rows.map((row) => (
            <label key={row.slotId} className="flex items-center gap-1 text-xs text-gray-600">
              {row.slotName}
              <Input
                type="number"
                min={0}
                className="w-20"
                value={values[row.slotId] ?? ''}
                onChange={(e) => onChange(row.slotId, e.target.value)}
              />
              {t('common.unit.minutes')}
            </label>
          ))}
        </div>
      )}
      <p className="text-xs text-gray-500">
        {t('dailyReport.studyLog.slotMinutesTotal', { minutes: sumSlotMinutes(values) })}
      </p>
      {addable.length > 0 && (
        <label className="flex items-center gap-1 text-xs text-gray-600">
          {t('dailyReport.studyLog.addSlotLabel')}
          <select
            className="rounded-md border border-gray-300 px-2 py-1 text-xs"
            value=""
            onChange={(e) => {
              if (e.target.value !== '') {
                onAddSlot(Number(e.target.value))
              }
            }}
          >
            <option value="">{t('dailyReport.studyLog.addSlotPlaceholder')}</option>
            {addable.map(([slotId, name]) => (
              <option key={slotId} value={slotId}>
                {name}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  )
}
