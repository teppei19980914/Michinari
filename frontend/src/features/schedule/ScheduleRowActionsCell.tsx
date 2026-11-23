import { t } from '../../locales/t'

/**
 * 行操作列（上へ・下へ・下に挿入・削除、D-13）。常に左端に固定し、固定する列数には数えない
 * （3.2）。閲覧のみの目標では表示しない（D-04）。
 */
export function ScheduleRowActionsCell({
  readOnly,
  canMoveUp,
  canMoveDown,
  onMoveUp,
  onMoveDown,
  onInsertBelow,
  onDelete,
}: {
  readOnly: boolean
  canMoveUp: boolean
  canMoveDown: boolean
  onMoveUp: () => void
  onMoveDown: () => void
  onInsertBelow: () => void
  onDelete: () => void
}) {
  if (readOnly) {
    return null
  }

  const handleDelete = () => {
    if (window.confirm(t('schedule.rowActions.deleteConfirm'))) {
      onDelete()
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-0.5">
      <button
        type="button"
        aria-label={t('schedule.rowActions.moveUp')}
        disabled={!canMoveUp}
        onClick={onMoveUp}
        className="rounded border border-border-strong px-1.5 py-0.5 text-xs text-text-secondary disabled:text-text-disabled"
      >
        ↑
      </button>
      <button
        type="button"
        aria-label={t('schedule.rowActions.moveDown')}
        disabled={!canMoveDown}
        onClick={onMoveDown}
        className="rounded border border-border-strong px-1.5 py-0.5 text-xs text-text-secondary disabled:text-text-disabled"
      >
        ↓
      </button>
      <button
        type="button"
        aria-label={t('schedule.rowActions.insertBelow')}
        onClick={onInsertBelow}
        className="rounded border border-border-strong px-1.5 py-0.5 text-xs text-text-secondary"
      >
        +
      </button>
      <button
        type="button"
        aria-label={t('schedule.rowActions.delete')}
        onClick={handleDelete}
        className="rounded border border-border-strong px-1.5 py-0.5 text-xs text-danger-text"
      >
        ×
      </button>
    </div>
  )
}
