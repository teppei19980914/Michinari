import { t } from '../../locales/t'
import { Input } from '../../components/Input'

/**
 * 追加列の見出し（D-12）。見出しのセルで名前を変更でき、左右への移動・削除を置く
 * （3.3）。削除時、値が入っている場合は確認文言を変える。
 */
export function ScheduleCustomColumnHeaderCell({
  name,
  readOnly,
  hasError,
  canMoveLeft,
  canMoveRight,
  hasAnyValue,
  onRename,
  onMoveLeft,
  onMoveRight,
  onDelete,
}: {
  name: string
  readOnly: boolean
  hasError?: boolean
  canMoveLeft: boolean
  canMoveRight: boolean
  hasAnyValue: boolean
  onRename: (name: string) => void
  onMoveLeft: () => void
  onMoveRight: () => void
  onDelete: () => void
}) {
  if (readOnly) {
    return <span className="text-xs font-medium text-text-primary">{name}</span>
  }

  const handleDelete = () => {
    const message = hasAnyValue
      ? t('schedule.customColumn.deleteConfirmWithValue')
      : t('schedule.customColumn.deleteConfirmEmpty')
    if (window.confirm(message)) {
      onDelete()
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Input
        value={name}
        placeholder={t('schedule.customColumn.namePlaceholder')}
        aria-label={t('schedule.customColumn.renameLabel')}
        onChange={(event) => onRename(event.target.value)}
        className={`text-xs ${hasError ? 'border-danger-text' : ''}`}
      />
      <div className="flex gap-0.5">
        <button
          type="button"
          aria-label={t('schedule.customColumn.moveLeft')}
          disabled={!canMoveLeft}
          onClick={onMoveLeft}
          className="rounded border border-border-strong px-1 text-xs text-text-secondary disabled:text-text-disabled"
        >
          ←
        </button>
        <button
          type="button"
          aria-label={t('schedule.customColumn.moveRight')}
          disabled={!canMoveRight}
          onClick={onMoveRight}
          className="rounded border border-border-strong px-1 text-xs text-text-secondary disabled:text-text-disabled"
        >
          →
        </button>
        <button
          type="button"
          aria-label={t('schedule.customColumn.delete')}
          onClick={handleDelete}
          className="rounded border border-border-strong px-1 text-xs text-danger-text"
        >
          ×
        </button>
      </div>
    </div>
  )
}
