import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import {
  createSlot,
  deleteSlot,
  listSlots,
  updateSlot,
  type ResourceSlotRead,
} from '../../api/resources'
import { SlotTimeFields, SlotWeekdaysField } from './SlotFormFields'
import type { SlotEnvironment } from './slotOptions'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 時間スロットの追加・編集フォーム。入力欄は SlotFormFields.tsx へ切り出してある
 * （CODING_RULES.md「保守性（複雑度）」）。
 *
 * 送信内容を決める判定（新規作成では有効/無効を送らず常に有効として作る・スロットの
 * 有無で作成と更新を呼び分ける）はこの関数に残す。 */
function SlotForm({ slot, onDone }: { slot?: ResourceSlotRead; onDone: () => void }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [name, setName] = useState(slot?.name ?? '')
  const [startTime, setStartTime] = useState(slot?.start_time ?? '07:00')
  const [endTime, setEndTime] = useState(slot?.end_time ?? '08:00')
  const [environment, setEnvironment] = useState<SlotEnvironment>(
    (slot?.environment as SlotEnvironment) ?? 'PC',
  )
  const [weekdays, setWeekdays] = useState<number[]>(slot?.weekdays ?? [])
  const [isActive, setIsActive] = useState(slot?.is_active ?? true)

  const toggleWeekday = (weekday: number) => {
    setWeekdays((current) =>
      current.includes(weekday) ? current.filter((w) => w !== weekday) : [...current, weekday],
    )
  }

  const mutation = useMutation({
    mutationFn: () => {
      const shared = {
        name,
        start_time: startTime,
        end_time: endTime,
        environment,
        weekdays,
      }
      // 有効/無効は編集でのみ送る（新規作成は常に有効なスロットとして作られる）。
      return slot ? updateSlot(slot.id, { ...shared, is_active: isActive }) : createSlot(shared)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.resourceSlots() })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.resourceAllocation() })
      onDone()
    },
    onError: showApiError,
  })

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('resources.slots.nameLabel')}
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <SlotTimeFields
        startTime={startTime}
        onChangeStartTime={setStartTime}
        endTime={endTime}
        onChangeEndTime={setEndTime}
        environment={environment}
        onChangeEnvironment={setEnvironment}
      />
      <SlotWeekdaysField weekdays={weekdays} onToggle={toggleWeekday} />
      {slot && (
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          {t('resources.slots.isActiveLabel')}
        </label>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>
          {t('common.action.cancel')}
        </Button>
        <Button type="submit" disabled={mutation.isPending || weekdays.length === 0}>
          {t('common.action.save')}
        </Button>
      </div>
    </form>
  )
}

/** 時間スロットの一覧・追加・編集・削除（仕様書6.3）。 */
export function SlotList() {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [addOpen, setAddOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  const slotsQuery = useQuery({ queryKey: QUERY_KEYS.resourceSlots(), queryFn: listSlots })

  const deleteMutation = useMutation({
    mutationFn: (slotId: number) => deleteSlot(slotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.resourceSlots() })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.resourceAllocation() })
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('resources.slots.title')}</h2>
      {slotsQuery.data?.length === 0 && !addOpen && (
        <p className="text-sm text-gray-500">{t('resources.slots.empty')}</p>
      )}
      {slotsQuery.data?.map((slot) =>
        editingId === slot.id ? (
          <div key={slot.id} className="rounded-md border border-gray-200 p-3">
            <SlotForm slot={slot} onDone={() => setEditingId(null)} />
          </div>
        ) : (
          <div
            key={slot.id}
            className={`flex items-center justify-between rounded-md border border-gray-200 p-3 ${
              slot.is_active ? '' : 'opacity-50'
            }`}
          >
            <div>
              <p className="text-sm font-medium text-gray-900">
                {slot.name} ({slot.start_time}〜{slot.end_time})
                {!slot.is_active && ` (${t('resources.slots.isActiveLabel')}: ${t('common.no')})`}
              </p>
              <p className="text-xs text-gray-500">
                {t(`goals.materials.environment.${slot.environment}`)} ·{' '}
                {slot.weekdays.map((w) => t(`resources.weekdays.${w}`)).join('')} ·{' '}
                {t('resources.slots.duration', {
                  minutes: slot.duration_minutes,
                  minutesUnit: t('common.unit.minutes'),
                  hours: slot.duration_hours,
                  hoursUnit: t('common.unit.hours'),
                })}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setEditingId(slot.id)}>
                {t('common.action.edit')}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  if (window.confirm(t('common.confirmDelete'))) {
                    deleteMutation.mutate(slot.id)
                  }
                }}
              >
                {t('common.action.delete')}
              </Button>
            </div>
          </div>
        ),
      )}
      {addOpen ? (
        <div className="rounded-md border border-gray-200 p-3">
          <SlotForm onDone={() => setAddOpen(false)} />
        </div>
      ) : (
        <Button variant="secondary" onClick={() => setAddOpen(true)}>
          {t('resources.slots.addTitle')}
        </Button>
      )}
    </Card>
  )
}
