import { useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import {
  getDayTypeDefaults,
  getHolidayCoverage,
  getHolidayTreatAsBuffer,
  importHolidaysFile,
  updateDayTypeDefaults,
  updateHolidayTreatAsBuffer,
  type DayType,
} from '../../api/resources'
import { WEEKDAYS } from './slotOptions'
import { QUERY_KEYS } from '../../constants/queryKeys'

//: 内閣府「国民の祝日」について（CSVのダウンロード元、D-46「データソースの案内」）。
const CABINET_OFFICE_HOLIDAY_INFO_URL = 'https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html'

/** 日種別の既定設定（仕様書6.3「曜日ごとに計画日またはバッファ日を選択」「祝日の扱い」）。 */
export function DayTypeDefaultsCard() {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const defaultsQuery = useQuery({
    queryKey: QUERY_KEYS.dayTypeDefaults(),
    queryFn: getDayTypeDefaults,
  })
  const holidayQuery = useQuery({
    queryKey: QUERY_KEYS.holidayTreatAsBuffer(),
    queryFn: getHolidayTreatAsBuffer,
  })
  const coverageQuery = useQuery({
    queryKey: QUERY_KEYS.holidayCoverage(),
    queryFn: () => getHolidayCoverage(),
  })

  const defaults = defaultsQuery.data ?? {}

  const dayTypeMutation = useMutation({
    mutationFn: ({ weekday, dayType }: { weekday: number; dayType: DayType }) =>
      updateDayTypeDefaults({ [weekday]: dayType }),
    meta: { overlay: 'saving' },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dayTypeDefaults() }),
    onError: showApiError,
  })

  const holidayMutation = useMutation({
    mutationFn: (value: boolean) => updateHolidayTreatAsBuffer(value),
    meta: { overlay: 'saving' },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.holidayTreatAsBuffer() }),
    onError: showApiError,
  })

  const importHolidaysMutation = useMutation({
    mutationFn: (file: File) => importHolidaysFile(file),
    meta: { overlay: 'saving' },
    onSuccess: (result) => {
      showToast(
        t('resources.dayTypeDefaults.importHolidaysSuccess', {
          count: result.imported_count,
          from: result.year_from,
          to: result.year_to,
        }),
      )
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.holidayCoverage() })
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-text-primary">{t('resources.dayTypeDefaults.title')}</h2>
      <div className="flex flex-wrap gap-3">
        {WEEKDAYS.map((weekday) => (
          <label key={weekday} className="flex flex-col items-center gap-1 text-sm text-text-secondary">
            {t(`resources.weekdays.${weekday}`)}
            <select
              className="rounded-md border border-border-strong px-2 py-1 text-sm"
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
        <label className="flex items-center gap-2 text-sm text-text-secondary">
          <input
            type="checkbox"
            checked={holidayQuery.data.treat_as_buffer}
            onChange={(e) => holidayMutation.mutate(e.target.checked)}
          />
          {t('resources.dayTypeDefaults.holidayTreatAsBuffer')}
        </label>
      )}
      <div className="flex flex-col gap-2 border-t border-border-strong pt-3">
        <h3 className="text-sm font-medium text-text-primary">
          {t('resources.dayTypeDefaults.holidayCoverageTitle')}
        </h3>
        <p className="text-sm text-text-secondary">
          {coverageQuery.data?.year_from != null && coverageQuery.data?.year_to != null
            ? t('resources.dayTypeDefaults.holidayCoverageRange', {
                from: coverageQuery.data.year_from,
                to: coverageQuery.data.year_to,
              })
            : t('resources.dayTypeDefaults.holidayCoverageNone')}
        </p>
        <p className="text-sm text-text-secondary">
          {t('resources.dayTypeDefaults.importHolidaysDescription')}
        </p>
        <div>
          <Button
            variant="secondary"
            disabled={importHolidaysMutation.isPending}
            onClick={() => fileInputRef.current?.click()}
          >
            {t('resources.dayTypeDefaults.importHolidaysButton')}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              e.target.value = ''
              if (!file) {
                return
              }
              importHolidaysMutation.mutate(file)
            }}
          />
        </div>
        <a
          href={CABINET_OFFICE_HOLIDAY_INFO_URL}
          target="_blank"
          rel="noreferrer"
          className="text-sm text-accent-muted-text underline"
        >
          {t('resources.dayTypeDefaults.cabinetOfficeLinkLabel')}
        </a>
      </div>
    </Card>
  )
}
