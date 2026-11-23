import { useEffect, useState } from 'react'
import { apiErrorMessage } from '../../api/client'
import { t } from '../../locales/t'
import { useToast } from '../../components/toastContext'
import { useUnsavedChangesWarning } from '../record/useUnsavedChangesWarning'
import { ScheduleConflictDialog } from './ScheduleConflictDialog'
import { ScheduleEmptyState } from './ScheduleEmptyState'
import { ScheduleGrid } from './ScheduleGrid'
import { ScheduleToolbar } from './ScheduleToolbar'
import { useScheduleEditorState } from './useScheduleEditorState'
import { useScheduleHolidays } from './useScheduleHolidays'
import { useScheduleSaveClick } from './useScheduleSaveClick'

/** スケジュールタブのエントリ（D-01・3.1）。`goalId`のみを受け取り自前で取得する
 * （`GanttTab.tsx`と同型）。幅の拡張（D-31）は`GoalDetailPage`側で`activeTab`を見て行う。 */
export function ScheduleTab({ goalId, readOnly }: { goalId: number; readOnly: boolean }) {
  const editor = useScheduleEditorState(goalId, readOnly)
  const { showApiError } = useToast()
  const [goToTodaySignal, setGoToTodaySignal] = useState(0)

  const { holidayIsoDates, holidayYearFrom, holidayYearTo } = useScheduleHolidays(
    editor.draft?.items ?? [],
    editor.today,
    editor.draft !== null,
  )

  useUnsavedChangesWarning(editor.hasUnsavedChanges)
  const handleSaveClick = useScheduleSaveClick(editor)

  useEffect(() => {
    if (editor.saveError && !editor.conflict) {
      showApiError(editor.saveError)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor.saveError, editor.conflict])

  if (editor.isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (editor.isError || !editor.draft || editor.today === null) {
    return <p className="text-sm text-danger-text">{apiErrorMessage(editor.error)}</p>
  }

  // 上のガード（!editor.draft）が通った時点で、同じGET応答から来るこれらの値も必ず
  // 非nullになる（useScheduleEditorState.ts、draftとmax_items等は同時に設定される）。
  const maxItems = editor.maxItems as number
  const maxCustomColumns = editor.maxCustomColumns as number
  const ganttDayWidthMinRem = editor.ganttDayWidthMinRem as number
  const ganttDayWidthMaxRem = editor.ganttDayWidthMaxRem as number

  const maxFrozenRowCount = editor.draft.items.length
  const maxFrozenColumnCount = 7 + editor.draft.columns.length
  const canAddRow = editor.draft.items.length < maxItems
  const canAddColumn = editor.draft.columns.length < maxCustomColumns

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-text-muted">{t('schedule.intro')}</p>
      <ScheduleToolbar
        readOnly={readOnly}
        frozenRowCount={editor.frozenRowCount}
        frozenColumnCount={editor.frozenColumnCount}
        maxFrozenRowCount={maxFrozenRowCount}
        maxFrozenColumnCount={maxFrozenColumnCount}
        canAddRow={canAddRow}
        canAddColumn={canAddColumn}
        hasUnsavedChanges={editor.hasUnsavedChanges}
        isSaving={editor.isSaving}
        maxItems={maxItems}
        maxCustomColumns={maxCustomColumns}
        onChangeFrozenRowCount={(count) => editor.updateFrozenCounts(count, editor.frozenColumnCount)}
        onChangeFrozenColumnCount={(count) => editor.updateFrozenCounts(editor.frozenRowCount, count)}
        onGoToToday={() => setGoToTodaySignal((signal) => signal + 1)}
        onAddRow={editor.addRow}
        onAddColumn={editor.addColumn}
        onDiscard={editor.discard}
        onSave={handleSaveClick}
      />

      {editor.draft.items.length === 0 ? (
        <ScheduleEmptyState readOnly={readOnly} onAddRow={editor.addRow} />
      ) : (
        <ScheduleGrid
          draft={editor.draft}
          readOnly={readOnly}
          frozenRowCount={editor.frozenRowCount}
          frozenColumnCount={editor.frozenColumnCount}
          today={editor.today}
          ganttDayWidthMinRem={ganttDayWidthMinRem}
          ganttDayWidthMaxRem={ganttDayWidthMaxRem}
          holidayIsoDates={holidayIsoDates}
          holidayYearFrom={holidayYearFrom}
          holidayYearTo={holidayYearTo}
          fieldErrorsByItemKey={editor.fieldErrorsByItemKey}
          columnErrorsByKey={editor.columnErrorsByKey}
          columnHasAnyValue={editor.columnHasAnyValue}
          goToTodaySignal={goToTodaySignal}
          onMoveRow={editor.moveRow}
          onInsertRowBelow={editor.insertRowBelow}
          onRemoveRow={editor.removeRow}
          onFieldChange={(itemKey, field, value) => editor.updateItem(itemKey, { [field]: value })}
          onStatusChange={editor.changeStatus}
          onCellChange={editor.updateCell}
          onRenameColumn={editor.renameColumn}
          onMoveColumn={editor.moveColumn}
          onRemoveColumn={editor.removeColumn}
        />
      )}

      <ScheduleConflictDialog
        open={editor.conflict}
        onReload={editor.resolveConflictReload}
        onKeepEditing={editor.resolveConflictKeepEditing}
      />
    </div>
  )
}
