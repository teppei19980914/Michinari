import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { DEFAULT_COLUMN_WIDTH_REM, stickyStyle } from './scheduleColumnLayout'
import { ScheduleDateCell } from './ScheduleDateCell'
import { ScheduleStatusSelect } from './ScheduleStatusSelect'
import type { ScheduleDraftFieldKey, ScheduleDraftItem } from './scheduleDraftTypes'
import type { ScheduleItemFieldErrors } from './scheduleValidation'

function autoResize(element: HTMLTextAreaElement): void {
  element.style.height = 'auto'
  element.style.height = `${element.scrollHeight}px`
}

/** 既定7列（作業項目・作業内容・予定開始日・予定終了日・状況・実績開始日・実績終了日）の
 * セル（D-08〜D-11、D-16）。`ScheduleDataRow`から分離（1関数100行の上限）。 */
export function ScheduleDefaultCells({
  item,
  readOnly,
  errors,
  leftOffsetsRem,
  onFieldChange,
  onStatusChange,
}: {
  item: ScheduleDraftItem
  readOnly: boolean
  errors: ScheduleItemFieldErrors
  leftOffsetsRem: (number | null)[]
  onFieldChange: (field: ScheduleDraftFieldKey, value: string | null) => void
  onStatusChange: (status: ScheduleDraftItem['status']) => void
}) {
  return (
    <>
      <div
        className="shrink-0 bg-surface p-1"
        style={{ width: `${DEFAULT_COLUMN_WIDTH_REM.title}rem`, ...stickyStyle(leftOffsetsRem[0]) }}
      >
        <Input
          value={item.title}
          disabled={readOnly}
          aria-label={t('schedule.columns.title')}
          onChange={(event) => onFieldChange('title', event.target.value)}
          className={`text-xs ${errors.title ? 'border-danger-text' : ''}`}
        />
        {errors.title && (
          <p className="text-xs text-danger-text">{t(`schedule.validation.${errors.title}`)}</p>
        )}
      </div>

      <div
        className="shrink-0 bg-surface p-1"
        style={{
          width: `${DEFAULT_COLUMN_WIDTH_REM.description}rem`,
          ...stickyStyle(leftOffsetsRem[1]),
        }}
      >
        <textarea
          value={item.description ?? ''}
          disabled={readOnly}
          rows={1}
          aria-label={t('schedule.columns.description')}
          onChange={(event) => {
            onFieldChange('description', event.target.value)
            autoResize(event.target)
          }}
          className="w-full resize-none rounded-md border border-border-strong px-2 py-1 text-xs"
        />
      </div>

      <ScheduleDateCell
        label={t('schedule.columns.plannedStartDate')}
        value={item.plannedStartDate}
        disabled={readOnly}
        hasError={Boolean(errors.plannedStartDate)}
        widthRem={DEFAULT_COLUMN_WIDTH_REM.plannedStartDate}
        leftRem={leftOffsetsRem[2]}
        onChange={(value) => onFieldChange('plannedStartDate', value)}
      />
      <ScheduleDateCell
        label={t('schedule.columns.plannedEndDate')}
        value={item.plannedEndDate}
        disabled={readOnly}
        hasError={Boolean(errors.plannedEndDate)}
        widthRem={DEFAULT_COLUMN_WIDTH_REM.plannedEndDate}
        leftRem={leftOffsetsRem[3]}
        onChange={(value) => onFieldChange('plannedEndDate', value)}
      />

      <div
        className="shrink-0 bg-surface p-1"
        style={{ width: `${DEFAULT_COLUMN_WIDTH_REM.status}rem`, ...stickyStyle(leftOffsetsRem[4]) }}
      >
        <ScheduleStatusSelect value={item.status} disabled={readOnly} onChange={onStatusChange} />
      </div>

      <ScheduleDateCell
        label={t('schedule.columns.actualStartDate')}
        value={item.actualStartDate}
        disabled={readOnly || item.status === 'NOT_STARTED'}
        hasError={Boolean(errors.actualStartDate)}
        widthRem={DEFAULT_COLUMN_WIDTH_REM.actualStartDate}
        leftRem={leftOffsetsRem[5]}
        onChange={(value) => onFieldChange('actualStartDate', value)}
      />
      <ScheduleDateCell
        label={t('schedule.columns.actualEndDate')}
        value={item.actualEndDate}
        disabled={readOnly || item.status === 'NOT_STARTED' || item.status === 'IN_PROGRESS'}
        hasError={Boolean(errors.actualEndDate)}
        widthRem={DEFAULT_COLUMN_WIDTH_REM.actualEndDate}
        leftRem={leftOffsetsRem[6]}
        onChange={(value) => onFieldChange('actualEndDate', value)}
      />
    </>
  )
}
