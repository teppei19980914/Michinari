import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { listSlotAllocations, updateSlotAllocations, type GoalDetailRead } from '../../api/goals'
import {
  buildSlotAllocationPayload,
  exceedsFreeMinutes,
  freeMinutes,
  initSlotAllocationValues,
  totalMinutes,
  type SlotAllocationFormValues,
} from './slotAllocationForm'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 1週間の日数（配分合計から1日あたりの平均を出すために使う）。 */
const DAYS_PER_WEEK = 7

/** リソース配分タブ（仕様書6.2「リソース配分タブの入力項目」。時間枠ごとに分で配分する）。 */
export function ResourceAllocationTab({
  goal,
  readOnly,
}: {
  goal: GoalDetailRead
  readOnly: boolean
}) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const query = useQuery({
    queryKey: QUERY_KEYS.goalSlotAllocations(goal.id),
    queryFn: () => listSlotAllocations(goal.id),
  })
  // 取得結果そのものではなく「利用者が編集した値」だけをstateに持つ。取得前・未編集の枠は
  // 取得結果から描画時に導出する（effectでのsetStateを避けるため）。
  const [edited, setEdited] = useState<SlotAllocationFormValues>({})

  const rows = query.data ?? []
  const values: SlotAllocationFormValues = { ...initSlotAllocationValues(rows), ...edited }
  const mutation = useMutation({
    mutationFn: () => updateSlotAllocations(goal.id, buildSlotAllocationPayload(rows, values)),
    onSuccess: () => {
      setEdited({})
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goalSlotAllocations(goal.id) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.resourceAllocation() })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goal(goal.id) })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const total = totalMinutes(values)

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('goals.resourceAllocation.title')}</h2>
      <p className="text-sm text-gray-500">{t('goals.resourceAllocation.description')}</p>
      {goal.category === 'READING' && (
        <p className="text-sm text-gray-500">
          {t('goals.resourceAllocation.optionalForReading')}
        </p>
      )}
      <Link to={ROUTES.resources} className="text-sm text-blue-600 hover:underline">
        {t('resources.title')}
      </Link>

      {rows.length === 0 ? (
        <p className="text-sm text-gray-500">{t('goals.resourceAllocation.noSlots')}</p>
      ) : (
        <>
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
                        onChange={(e) =>
                          setEdited((current) => ({ ...current, [row.slot_id]: e.target.value }))
                        }
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

          <p className="text-sm text-gray-700">
            {t('goals.resourceAllocation.totalLabel')}: {total}
            {t('common.unit.minutes')}{' '}
            <span className="text-gray-500">
              {t('goals.resourceAllocation.averagePerDay', {
                minutes: Math.floor(total / DAYS_PER_WEEK),
              })}
            </span>
          </p>

          {!readOnly && (
            <div className="flex justify-end">
              <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
                {t('common.action.save')}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
