import type { ScheduleRevisionProposalItemRead, ScheduleRevisionProposalRead } from '../../api/schedule'
import type { ScheduleDraft, ScheduleDraftItem } from './scheduleDraftTypes'
import type { useScheduleEditorState } from './useScheduleEditorState'
import type { EditedDates } from './useScheduleRevisionEditedDates'

/** 作業項目id→作業項目名の対応表（修正案パネルの行の表題に使う、単位5・13.8）。
 * `ScheduleTab`を1関数100行以内に収めるための分離（CODING_RULES.md「保守性（複雑度）」）。 */
export function buildItemTitleById(items: ScheduleDraftItem[]): Record<number, string> {
  const result: Record<number, string> = {}
  for (const item of items) {
    if (item.id !== null) result[item.id] = item.title
  }
  return result
}

/** 未判断の変更行（stale除く）だけをガントへ点線で重ねるための対応表（D-57）。日付を手で
 * 修正した場合は`datesFor`（`ScheduleRevisionPanel`と共有）の編集後の値を使う。 */
export function buildProposedBandByItemId(
  proposal: ScheduleRevisionProposalRead | null,
  datesFor: (item: ScheduleRevisionProposalItemRead) => EditedDates,
): Record<number, EditedDates> {
  const result: Record<number, EditedDates> = {}
  if (!proposal) {
    return result
  }
  for (const proposalItem of proposal.items) {
    if (
      proposalItem.kind === 'CHANGE' &&
      proposalItem.decision === 'PENDING' &&
      !proposalItem.is_stale
    ) {
      result[proposalItem.schedule_item_id] = datesFor(proposalItem)
    }
  }
  return result
}

/** `ScheduleTab`の行・列の上限・追加可否の算出（D-04・D-05等）。`ScheduleTab`を1関数
 * 100行以内に収めるための分離（CODING_RULES.md「保守性（複雑度）」）。 */
export function buildScheduleTabLayout(
  editor: ReturnType<typeof useScheduleEditorState>,
  draft: ScheduleDraft,
) {
  const maxItems = editor.maxItems as number
  const maxCustomColumns = editor.maxCustomColumns as number
  const ganttDayWidthMinRem = editor.ganttDayWidthMinRem as number
  const ganttDayWidthMaxRem = editor.ganttDayWidthMaxRem as number
  return {
    maxItems,
    maxCustomColumns,
    ganttDayWidthMinRem,
    ganttDayWidthMaxRem,
    maxFrozenRowCount: draft.items.length,
    maxFrozenColumnCount: 7 + draft.columns.length,
    canAddRow: draft.items.length < maxItems,
    canAddColumn: draft.columns.length < maxCustomColumns,
  }
}
