/** リソース配分タブ（ResourceAllocationTab.tsx）の時間枠ごとの配分表。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた
 * ResourceAllocationTab から、表の描画だけを切り出したものである。入力値の保持と保存は
 * 呼び出し元に残し、ここは受け取った値を並べて変更を返すことに徹する。 */
import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import type { SlotAllocationRead } from '../../api/goals'
import {
  exceedsFreeMinutes,
  freeMinutes,
  type SlotAllocationFormValues,
} from './slotAllocationForm'

export function SlotAllocationTable({
  rows,
  values,
  readOnly,
  onChangeMinutes,
}: {
  rows: SlotAllocationRead[]
  values: SlotAllocationFormValues
  readOnly: boolean
  onChangeMinutes: (slotId: number, minutes: string) => void
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-500">
            <th className="py-1 pr-3">{t('goals.resourceAllocation.slotColumn')}</th>
            <th className="py-1 pr-3">{t('goals.resourceAllocation.freeColumn')}</th>
            <th className="py-1">{t('goals.resourceAllocation.minutesColumn')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.slot_id} className="border-t border-gray-100">
              <td className="py-2 pr-3 align-top">
                <p className="text-gray-900">{row.slot_name}</p>
                <p className="text-xs text-gray-500">
                  {t(`goals.materials.environment.${row.environment}`)} ·{' '}
                  {row.weekdays.map((w) => t(`resources.weekdays.${w}`)).join('')} ·{' '}
                  {row.duration_minutes}
                  {t('common.unit.minutes')}
                </p>
                {row.is_over_capacity && (
                  <p className="text-xs text-red-600">
                    {t('goals.resourceAllocation.overCapacity')}
                  </p>
                )}
              </td>
              <td className="py-2 pr-3 align-top text-gray-700">
                {freeMinutes(row)}
                {t('common.unit.minutes')}
              </td>
              <td className="py-2 align-top">
                <Input
                  type="number"
                  min={0}
                  className="w-24"
                  /* v8 ignore next -- values は initSlotAllocationValues が rows の
                     全 slot_id を必ず埋めるため undefined にならない。値が未設定でも
                     入力欄が非制御へ切り替わらないようにするための防御であり、
                     テストからは到達できない（OPERATIONS.md「到達不能な防御的分岐」）。 */
                  value={values[row.slot_id] ?? ''}
                  disabled={readOnly}
                  onChange={(e) => onChangeMinutes(row.slot_id, e.target.value)}
                />
                {exceedsFreeMinutes(row, values[row.slot_id]) && (
                  <p className="mt-1 text-xs text-red-600">
                    {t('goals.resourceAllocation.exceeded')}
                  </p>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
