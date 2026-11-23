import { t } from '../../locales/t'
import type { ScheduleItemStatus } from '../../api/schedule'

const STATUSES: ScheduleItemStatus[] = ['NOT_STARTED', 'IN_PROGRESS', 'DONE', 'CANCELLED']

/**
 * 状況の選択（D-10）。状況の変更そのものによる実績日の補完（6.3）は、呼び出し側
 * （`useScheduleEditorState`）が`onChange`を受けて行う（この部品は見た目のみ）。
 */
export function ScheduleStatusSelect({
  value,
  disabled,
  hasError,
  onChange,
}: {
  value: ScheduleItemStatus
  disabled: boolean
  hasError?: boolean
  onChange: (next: ScheduleItemStatus) => void
}) {
  return (
    <select
      value={value}
      disabled={disabled}
      aria-label={t('schedule.columns.status')}
      onChange={(event) => onChange(event.target.value as ScheduleItemStatus)}
      className={`rounded-md border px-2 py-1 text-xs ${
        hasError ? 'border-danger-text' : 'border-border-strong'
      }`}
    >
      {STATUSES.map((status) => (
        <option key={status} value={status}>
          {t(`schedule.status.${status}`)}
        </option>
      ))}
    </select>
  )
}
