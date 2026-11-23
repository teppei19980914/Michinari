import { useMutation, type QueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { saveSchedule, updateScheduleViewSetting, type ScheduleRead } from '../../api/schedule'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { buildSaveRequest, toDraft, type ScheduleDraft } from './scheduleDraftTypes'

/**
 * 保存系の2つのミューテーション（一括保存・固定設定）。`useScheduleEditorState`から
 * 分離（1関数100行の上限、CODING_RULES.md「保守性」）。
 */
export function useScheduleSaveMutations(
  goalId: number,
  queryClient: QueryClient,
  applyServerData: (data: ScheduleRead) => void,
  onConflict: () => void,
) {
  const saveMutation = useMutation({
    mutationFn: (payload: ReturnType<typeof buildSaveRequest>) => saveSchedule(goalId, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEYS.schedule(goalId), data)
      applyServerData(data)
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.code === 'SCHEDULE_REVISION_CONFLICT') {
        onConflict()
      }
    },
  })

  const viewSettingMutation = useMutation({
    mutationFn: (payload: { frozen_row_count: number; frozen_column_count: number }) =>
      updateScheduleViewSetting(goalId, payload),
  })

  return { saveMutation, viewSettingMutation }
}

/** `applyServerData`の既定実装（draft/baselineの両方を同じサーバー値へ揃える）。 */
export function applyScheduleServerData(
  data: ScheduleRead,
  setDraft: (next: ScheduleDraft) => void,
  setBaseline: (next: ScheduleDraft) => void,
  setFrozenRowCount: (count: number) => void,
  setFrozenColumnCount: (count: number) => void,
): void {
  const next = toDraft(data)
  setDraft(next)
  setBaseline(next)
  setFrozenRowCount(data.frozen_row_count)
  setFrozenColumnCount(data.frozen_column_count)
}
