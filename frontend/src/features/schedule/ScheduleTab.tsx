import { useState } from 'react'
import { apiErrorMessage } from '../../api/client'
import { t } from '../../locales/t'
import { useUnsavedChangesWarning } from '../record/useUnsavedChangesWarning'
import { ScheduleConflictDialog } from './ScheduleConflictDialog'
import { ScheduleEmptyState } from './ScheduleEmptyState'
import { ScheduleGrid } from './ScheduleGrid'
import { ScheduleRevisionPanel } from './ScheduleRevisionPanel'
import {
  buildItemTitleById,
  buildProposedBandByItemId,
  buildScheduleTabLayout,
} from './scheduleRevisionBandMapping'
import { ScheduleToolbar } from './ScheduleToolbar'
import { useScheduleEditorState } from './useScheduleEditorState'
import { useScheduleHolidays } from './useScheduleHolidays'
import { useScheduleRevision } from './useScheduleRevision'
import { useScheduleRevisionEditedDates } from './useScheduleRevisionEditedDates'
import { useScheduleSaveClick } from './useScheduleSaveClick'
import { useScheduleTabErrorToasts } from './useScheduleTabErrorToasts'

/** スケジュールタブのエントリ（D-01・3.1）。`goalId`のみを受け取り自前で取得する
 * （`GanttTab.tsx`と同型）。幅の拡張（D-31）は`GoalDetailPage`側で`activeTab`を見て行う。 */
export function ScheduleTab({ goalId, readOnly }: { goalId: number; readOnly: boolean }) {
  const editor = useScheduleEditorState(goalId, readOnly)
  const [goToTodaySignal, setGoToTodaySignal] = useState(0)
  const revision = useScheduleRevision(goalId)
  const { datesFor, setDates } = useScheduleRevisionEditedDates()

  const { holidayIsoDates, holidayYearFrom, holidayYearTo } = useScheduleHolidays(
    editor.draft?.items ?? [],
    editor.today,
    editor.draft !== null,
  )

  useUnsavedChangesWarning(editor.hasUnsavedChanges)
  const handleSaveClick = useScheduleSaveClick(editor)
  useScheduleTabErrorToasts(editor, revision)

  if (editor.isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (editor.isError || !editor.draft || editor.today === null) {
    return <p className="text-sm text-danger-text">{apiErrorMessage(editor.error)}</p>
  }

  // 上のガード（!editor.draft）が通った時点で、同じGET応答から来るmax_items等の値も必ず
  // 非nullになる（useScheduleEditorState.ts、draftとmax_items等は同時に設定される）。
  const draft = editor.draft
  const layout = buildScheduleTabLayout(editor, draft)
  const proposal = editor.pendingRevisionProposal
  const itemTitleById = buildItemTitleById(draft.items)
  const proposedBandByItemId = buildProposedBandByItemId(proposal, datesFor)

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-text-muted">{t('schedule.intro')}</p>
      <ScheduleToolbar
        readOnly={readOnly}
        frozenRowCount={editor.frozenRowCount}
        frozenColumnCount={editor.frozenColumnCount}
        maxFrozenRowCount={layout.maxFrozenRowCount}
        maxFrozenColumnCount={layout.maxFrozenColumnCount}
        canAddRow={layout.canAddRow}
        canAddColumn={layout.canAddColumn}
        hasUnsavedChanges={editor.hasUnsavedChanges}
        isSaving={editor.isSaving}
        maxItems={layout.maxItems}
        maxCustomColumns={layout.maxCustomColumns}
        isRequestingRevision={revision.isRequesting}
        onChangeFrozenRowCount={(count) => editor.updateFrozenCounts(count, editor.frozenColumnCount)}
        onChangeFrozenColumnCount={(count) => editor.updateFrozenCounts(editor.frozenRowCount, count)}
        onGoToToday={() => setGoToTodaySignal((signal) => signal + 1)}
        onAddRow={editor.addRow}
        onAddColumn={editor.addColumn}
        onDiscard={editor.discard}
        onSave={handleSaveClick}
        onRequestRevision={revision.requestRevision}
      />

      {proposal && (
        <ScheduleRevisionPanel
          proposal={proposal}
          itemTitleById={itemTitleById}
          canDecide={!editor.hasUnsavedChanges}
          isDeciding={revision.isDeciding}
          datesFor={datesFor}
          setDates={setDates}
          onDecide={(decisions) => revision.decide(proposal.id, decisions)}
        />
      )}

      {draft.items.length === 0 ? (
        <ScheduleEmptyState readOnly={readOnly} onAddRow={editor.addRow} />
      ) : (
        <ScheduleGrid
          draft={draft}
          readOnly={readOnly}
          frozenRowCount={editor.frozenRowCount}
          frozenColumnCount={editor.frozenColumnCount}
          today={editor.today}
          ganttDayWidthMinRem={layout.ganttDayWidthMinRem}
          ganttDayWidthMaxRem={layout.ganttDayWidthMaxRem}
          holidayIsoDates={holidayIsoDates}
          holidayYearFrom={holidayYearFrom}
          holidayYearTo={holidayYearTo}
          fieldErrorsByItemKey={editor.fieldErrorsByItemKey}
          columnErrorsByKey={editor.columnErrorsByKey}
          columnHasAnyValue={editor.columnHasAnyValue}
          goToTodaySignal={goToTodaySignal}
          proposedBandByItemId={proposedBandByItemId}
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
