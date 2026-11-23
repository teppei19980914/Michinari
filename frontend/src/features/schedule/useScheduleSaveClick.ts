import { useToast } from '../../components/toastContext'
import { t } from '../../locales/t'
import type { useScheduleEditorState } from './useScheduleEditorState'

/**
 * 保存ボタンの押下処理（D-29）。検証エラーがある場合は保存を行わず、件数を知らせて
 * 最初のエラーのセル（行）まで自動でスクロールする。エラーが無ければ通常の保存を行う。
 */
export function useScheduleSaveClick(editor: ReturnType<typeof useScheduleEditorState>) {
  const { showToast } = useToast()

  return function handleSaveClick() {
    if (!editor.hasFieldErrors) {
      editor.save()
      return
    }

    const errorCount =
      Object.keys(editor.fieldErrorsByItemKey).length + Object.keys(editor.columnErrorsByKey).length
    showToast(t('schedule.validation.saveErrorCount', { count: errorCount }), 'error')

    const firstErrorKey = Object.keys(editor.fieldErrorsByItemKey)[0]
    if (firstErrorKey) {
      document
        .querySelector(`[data-item-key="${firstErrorKey}"]`)
        ?.scrollIntoView({ block: 'center' })
    }
  }
}
