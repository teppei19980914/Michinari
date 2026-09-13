import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { useToast } from '../../components/Toast'
import {
  getDayTypeDefaults,
  getHolidayTreatAsBuffer,
  updateDayTypeDefaults,
  updateHolidayTreatAsBuffer,
  type DayType,
} from '../../api/resources'
import { QUERY_KEYS } from '../../constants/queryKeys'

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6] as const

/** 日種別の既定設定（仕様書6.3「曜日ごとに計画日またはバッファ日を選択」「祝日の扱い」）。 */
export function DayTypeDefaultsCard() {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const defaultsQuery = useQuery({
    queryKey: QUERY_KEYS.dayTypeDefaults(),
    queryFn: getDayTypeDefaults,
  })
  const holidayQuery = useQuery({
    queryKey: QUERY_KEYS.holidayTreatAsBuffer(),
    queryFn: getHolidayTreatAsBuffer,
  })

  const defaults = defaultsQuery.data ?? {}

  const dayTypeMutation = useMutation({
    mutationFn: ({ weekday, dayType }: { weekday: number; dayType: DayType }) =>
      updateDayTypeDefaults({ [weekday]: dayType }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dayTypeDefaults() }),
    onError: showApiError,
  })

  const holidayMutation = useMutation({
    mutationFn: (value: boolean) => updateHolidayTreatAsBuffer(value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.holidayTreatAsBuffer() }),
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('resources.dayTypeDefaults.title')}</h2>
      <div className="flex flex-wrap gap-3">
        {WEEKDAYS.map((weekday) => (
          <label key={weekday} className="flex flex-col items-center gap-1 text-sm text-gray-700">
            {t(`resources.weekdays.${weekday}`)}
            <select
              className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              value={defaults[weekday] ?? 'PLAN'}
              onChange={(e) =>
                dayTypeMutation.mutate({ weekday, dayType: e.target.value as DayType })
              }
            >
              <option value="PLAN">{t('resources.dayTypeDefaults.plan')}</option>
              <option value="BUFFER">{t('resources.dayTypeDefaults.buffer')}</option>
            </select>
          </label>
        ))}
      </div>
      {holidayQuery.data && (
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={holidayQuery.data.treat_as_buffer}
            onChange={(e) => holidayMutation.mutate(e.target.checked)}
          />
          {t('resources.dayTypeDefaults.holidayTreatAsBuffer')}
        </label>
      )}
    </Card>
  )
}
