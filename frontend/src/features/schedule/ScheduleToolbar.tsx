import { t } from '../../locales/t'
import { Button } from '../../components/Button'

export type ScheduleToolbarProps = {
  readOnly: boolean
  frozenRowCount: number
  frozenColumnCount: number
  maxFrozenRowCount: number
  maxFrozenColumnCount: number
  canAddRow: boolean
  canAddColumn: boolean
  hasUnsavedChanges: boolean
  isSaving: boolean
  maxItems: number
  maxCustomColumns: number
  //: 「AIに修正案を依頼」ボタン（D-58、単位5）。生成中は無効化、終了した目標では非表示。
  isRequestingRevision: boolean
  onChangeFrozenRowCount: (count: number) => void
  onChangeFrozenColumnCount: (count: number) => void
  onGoToToday: () => void
  onAddRow: () => void
  onAddColumn: () => void
  onDiscard: () => void
  onSave: () => void
  onRequestRevision: () => void
}

function frozenCountOptions(max: number): number[] {
  return Array.from({ length: max + 1 }, (_, count) => count)
}

/** スケジュールタブのツールバー（3.1・D-24〜D-26）。 */
export function ScheduleToolbar({
  readOnly,
  frozenRowCount,
  frozenColumnCount,
  maxFrozenRowCount,
  maxFrozenColumnCount,
  canAddRow,
  canAddColumn,
  hasUnsavedChanges,
  isSaving,
  maxItems,
  maxCustomColumns,
  isRequestingRevision,
  onChangeFrozenRowCount,
  onChangeFrozenColumnCount,
  onGoToToday,
  onAddRow,
  onAddColumn,
  onDiscard,
  onSave,
  onRequestRevision,
}: ScheduleToolbarProps) {
  function handleDiscard() {
    if (window.confirm(t('schedule.toolbar.discardConfirm'))) {
      onDiscard()
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface-muted p-2">
      <label className="flex items-center gap-1 text-xs text-text-secondary">
        {t('schedule.toolbar.frozenRowsLabel')}
        <select
          value={frozenRowCount}
          disabled={readOnly}
          onChange={(event) => onChangeFrozenRowCount(Number(event.target.value))}
          className="rounded-md border border-border-strong px-2 py-1 text-xs"
        >
          {frozenCountOptions(maxFrozenRowCount).map((count) => (
            <option key={count} value={count}>
              {count}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1 text-xs text-text-secondary">
        {t('schedule.toolbar.frozenColumnsLabel')}
        <select
          value={frozenColumnCount}
          disabled={readOnly}
          onChange={(event) => onChangeFrozenColumnCount(Number(event.target.value))}
          className="rounded-md border border-border-strong px-2 py-1 text-xs"
        >
          {frozenCountOptions(maxFrozenColumnCount).map((count) => (
            <option key={count} value={count}>
              {count}
            </option>
          ))}
        </select>
      </label>

      <Button variant="secondary" onClick={onGoToToday}>
        {t('schedule.toolbar.goToToday')}
      </Button>

      {!readOnly && (
        <>
          <Button variant="secondary" disabled={!canAddRow} onClick={onAddRow}>
            {t('schedule.toolbar.addRow')}
          </Button>
          <Button variant="secondary" disabled={!canAddColumn} onClick={onAddColumn}>
            {t('schedule.toolbar.addColumn')}
          </Button>
          {!canAddRow && (
            <p className="text-xs text-text-faint">
              {t('schedule.toolbar.rowLimitReached', { max: maxItems })}
            </p>
          )}
          {!canAddColumn && (
            <p className="text-xs text-text-faint">
              {t('schedule.toolbar.columnLimitReached', { max: maxCustomColumns })}
            </p>
          )}
          <Button variant="secondary" disabled={!hasUnsavedChanges} onClick={handleDiscard}>
            {t('schedule.toolbar.discardChanges')}
          </Button>
          <Button variant="secondary" disabled={isRequestingRevision} onClick={onRequestRevision}>
            {t('schedule.toolbar.requestRevision')}
          </Button>
          <Button variant="primary" disabled={!hasUnsavedChanges || isSaving} onClick={onSave}>
            {t('schedule.toolbar.save')}
          </Button>
        </>
      )}
    </div>
  )
}
