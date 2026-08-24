import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { getDayBoundaryHour, updateDayBoundaryHour } from '../../api/resources'

/** 1日の境界時刻（仕様書6.3「日付が切り替わる時刻」）。 */
export function DayBoundaryHourCard() {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const query = useQuery({ queryKey: ['day-boundary-hour'], queryFn: getDayBoundaryHour })
  const [hour, setHour] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (value: number) => updateDayBoundaryHour(value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['day-boundary-hour'] })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const value = hour ?? String(query.data?.day_boundary_hour ?? 0)

  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-gray-900">{t('resources.dayBoundaryHour.title')}</h2>
      <p className="text-xs text-gray-500">{t('resources.dayBoundaryHour.description')}</p>
      <div className="flex items-end gap-2">
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('resources.dayBoundaryHour.label')}
          <Input
            type="number"
            min={0}
            max={11}
            value={value}
            onChange={(e) => setHour(e.target.value)}
          />
        </label>
        <Button disabled={mutation.isPending} onClick={() => mutation.mutate(Number(value))}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}
