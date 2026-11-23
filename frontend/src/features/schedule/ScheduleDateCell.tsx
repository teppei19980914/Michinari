import { Input } from '../../components/Input'
import { stickyStyle } from './scheduleColumnLayout'

/** 日付セル（予定開始日・予定終了日・実績開始日・実績終了日で共通、D-09〜D-11）。 */
export function ScheduleDateCell({
  label,
  value,
  disabled,
  hasError,
  widthRem,
  leftRem,
  onChange,
}: {
  label: string
  value: string | null
  disabled: boolean
  hasError: boolean
  widthRem: number
  leftRem: number | null
  onChange: (value: string | null) => void
}) {
  return (
    <div className="shrink-0 bg-surface p-1" style={{ width: `${widthRem}rem`, ...stickyStyle(leftRem) }}>
      <Input
        type="date"
        value={value ?? ''}
        disabled={disabled}
        aria-label={label}
        onChange={(event) => onChange(event.target.value || null)}
        className={`text-xs ${hasError ? 'border-danger-text' : ''}`}
      />
    </div>
  )
}
