import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Modal } from '../../components/Modal'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { clearDayType, setDayType } from '../../api/calendar'
import type { DayType } from '../../api/calendar'
import { QUERY_KEYS } from '../../constants/queryKeys'

const DAY_TYPES: DayType[] = ['PLAN', 'BUFFER', 'OFF']

/** 日種別変更モーダル（仕様書6.4「日種別変更: 全ての日、カレンダー内で処理」）。 */
export function DayTypeEditModal({
  targetDate,
  onClose,
}: {
  targetDate: string | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()

  const setMutation = useMutation({
    mutationFn: (dayType: DayType) => setDayType(targetDate as string, { day_type: dayType }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.calendar() })
      onClose()
    },
    onError: showApiError,
  })
  const clearMutation = useMutation({
    mutationFn: () => clearDayType(targetDate as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.calendar() })
      onClose()
    },
    onError: showApiError,
  })

  return (
    <Modal open={targetDate !== null} onClose={onClose} title={t('calendar.dayTypeModal.title')}>
      <p className="text-sm text-gray-600">
        {t('calendar.dayTypeModal.targetDateLabel')}: {targetDate}
      </p>
      <div className="mt-4 flex flex-col gap-2">
        {DAY_TYPES.map((dayType) => (
          <Button
            key={dayType}
            variant="secondary"
            disabled={setMutation.isPending}
            onClick={() => setMutation.mutate(dayType)}
          >
            {t(`calendar.dayType.${dayType}`)}
          </Button>
        ))}
        <Button
          variant="secondary"
          disabled={clearMutation.isPending}
          onClick={() => clearMutation.mutate()}
        >
          {t('calendar.dayTypeModal.clearOverride')}
        </Button>
      </div>
    </Modal>
  )
}
