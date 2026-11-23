import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getSchedule } from '../../api/schedule'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { useScheduleRowActions } from './useScheduleRowActions'
import { useScheduleColumnActions } from './useScheduleColumnActions'
import { applyScheduleServerData, useScheduleSaveMutations } from './useScheduleSaveMutations'
import { buildSaveRequest, draftContentEquals, type ScheduleDraft } from './scheduleDraftTypes'
import {
  hasScheduleFieldErrors,
  validateScheduleItemFields,
  type ScheduleItemFieldErrors,
} from './scheduleValidation'

/** 1行分の検証エラー（D-09〜D-11）を、本日を基準にドラフト全体から算出する。 */
function useFieldErrors(draft: ScheduleDraft | null, today: string | null) {
  return useMemo<Record<string, ScheduleItemFieldErrors>>(() => {
    if (!draft || !today) return {}
    const result: Record<string, ScheduleItemFieldErrors> = {}
    for (const item of draft.items) {
      const errors = validateScheduleItemFields(
        {
          title: item.title,
          plannedStartDate: item.plannedStartDate,
          plannedEndDate: item.plannedEndDate,
          status: item.status,
          actualStartDate: item.actualStartDate,
          actualEndDate: item.actualEndDate,
        },
        today,
      )
      if (hasScheduleFieldErrors(errors)) {
        result[item.key] = errors
      }
    }
    return result
  }, [draft, today])
}

/** 追加列の名前の検証（必須・重複不可、D-12）をドラフト全体から算出する。 */
function useColumnErrors(draft: ScheduleDraft | null) {
  return useMemo<Record<string, 'NAME_REQUIRED' | 'DUPLICATE_NAME'>>(() => {
    if (!draft) return {}
    const result: Record<string, 'NAME_REQUIRED' | 'DUPLICATE_NAME'> = {}
    const seen = new Set<string>()
    for (const column of draft.columns) {
      if (!column.name.trim()) {
        result[column.key] = 'NAME_REQUIRED'
        continue
      }
      if (seen.has(column.name)) {
        result[column.key] = 'DUPLICATE_NAME'
      }
      seen.add(column.name)
    }
    return result
  }, [draft])
}

/**
 * スケジュールタブの編集状態（開発Todo_スケジュール・ガントチャート_v1.1 D-05〜D-13）。
 *
 * `draft`（行・追加列・セル）は一括保存（D-05・D-06）の対象で、`baseline`との差分で
 * 未保存の変更を判定する（D-05後段「未保存のまま画面を離れる際は警告」）。固定行数・
 * 列数（D-24・D-25）は別API（`PUT .../view-setting`）で即時保存するため、`draft`には
 * 含めず未保存判定の対象外とする（本書7.1「固定の設定の変更ではrevisionを増やさない」）。
 * 行・列の編集操作・保存系ミューテーションは別フックへ分離している（複雑度対策）。
 *
 * @param goalId 対象の目標ID
 * @param readOnly 終了した目標かどうか（`isClosedGoalStatus`、呼び出し元が判定して渡す）
 * @returns 読み込み状態・ドラフト・検証エラー・編集操作・保存系の操作をまとめたオブジェクト
 */
export function useScheduleEditorState(goalId: number, readOnly: boolean) {
  const queryClient = useQueryClient()

  const scheduleQuery = useQuery({
    queryKey: QUERY_KEYS.schedule(goalId),
    queryFn: () => getSchedule(goalId),
  })

  const [draft, setDraft] = useState<ScheduleDraft | null>(null)
  const [baseline, setBaseline] = useState<ScheduleDraft | null>(null)
  const [frozenRowCount, setFrozenRowCount] = useState(0)
  const [frozenColumnCount, setFrozenColumnCount] = useState(1)
  const [conflict, setConflict] = useState(false)

  if (scheduleQuery.data && draft === null) {
    applyScheduleServerData(
      scheduleQuery.data,
      setDraft,
      setBaseline,
      setFrozenRowCount,
      setFrozenColumnCount,
    )
  }

  const today = scheduleQuery.data?.today ?? null
  const rowActions = useScheduleRowActions(draft, setDraft, today)
  const columnActions = useScheduleColumnActions(draft, setDraft)

  const { saveMutation, viewSettingMutation } = useScheduleSaveMutations(
    goalId,
    queryClient,
    (data) =>
      applyScheduleServerData(data, setDraft, setBaseline, setFrozenRowCount, setFrozenColumnCount),
    () => setConflict(true),
  )

  const hasUnsavedChanges =
    draft !== null && baseline !== null && !draftContentEquals(draft, baseline)

  const fieldErrorsByItemKey = useFieldErrors(draft, today)
  const columnErrorsByKey = useColumnErrors(draft)
  const hasFieldErrors =
    Object.keys(fieldErrorsByItemKey).length > 0 || Object.keys(columnErrorsByKey).length > 0

  function save() {
    if (!draft || hasFieldErrors) return
    saveMutation.mutate(buildSaveRequest(draft))
  }

  function discard() {
    if (baseline) {
      setDraft(baseline)
    }
  }

  function updateFrozenCounts(nextFrozenRowCount: number, nextFrozenColumnCount: number) {
    setFrozenRowCount(nextFrozenRowCount)
    setFrozenColumnCount(nextFrozenColumnCount)
    viewSettingMutation.mutate({
      frozen_row_count: nextFrozenRowCount,
      frozen_column_count: nextFrozenColumnCount,
    })
  }

  async function resolveConflictReload() {
    const { data } = await scheduleQuery.refetch()
    if (data) {
      applyScheduleServerData(data, setDraft, setBaseline, setFrozenRowCount, setFrozenColumnCount)
    }
    setConflict(false)
  }

  function resolveConflictKeepEditing() {
    setConflict(false)
  }

  return {
    isLoading: scheduleQuery.isLoading,
    isError: scheduleQuery.isError,
    error: scheduleQuery.error,
    today,
    maxItems: scheduleQuery.data?.max_items ?? null,
    maxCustomColumns: scheduleQuery.data?.max_custom_columns ?? null,
    ganttDayWidthMinRem: scheduleQuery.data?.gantt_day_width_min_rem ?? null,
    ganttDayWidthMaxRem: scheduleQuery.data?.gantt_day_width_max_rem ?? null,
    draft,
    readOnly,
    frozenRowCount,
    frozenColumnCount,
    fieldErrorsByItemKey,
    columnErrorsByKey,
    hasFieldErrors,
    hasUnsavedChanges,
    conflict,
    isSaving: saveMutation.isPending,
    saveError: saveMutation.error,
    ...rowActions,
    ...columnActions,
    updateFrozenCounts,
    save,
    discard,
    resolveConflictReload,
    resolveConflictKeepEditing,
  }
}
