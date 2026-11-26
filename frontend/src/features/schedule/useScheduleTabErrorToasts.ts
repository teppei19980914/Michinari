import { useEffect } from 'react'
import { useToast } from '../../components/toastContext'
import type { useScheduleEditorState } from './useScheduleEditorState'
import type { useScheduleRevision } from './useScheduleRevision'

/** `ScheduleTab`のエラートースト（保存・修正案の生成・判断）を1箇所にまとめる。
 * `ScheduleTab`を1関数100行以内に収めるための分離（CODING_RULES.md「保守性（複雑度）」）。 */
export function useScheduleTabErrorToasts(
  editor: ReturnType<typeof useScheduleEditorState>,
  revision: ReturnType<typeof useScheduleRevision>,
) {
  const { showApiError } = useToast()

  useEffect(() => {
    if (editor.saveError && !editor.conflict) {
      showApiError(editor.saveError)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor.saveError, editor.conflict])

  useEffect(() => {
    if (revision.requestError) {
      showApiError(revision.requestError)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revision.requestError])

  useEffect(() => {
    if (revision.decideError) {
      showApiError(revision.decideError)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revision.decideError])
}
