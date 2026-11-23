import { t } from '../../locales/t'
import { Modal } from '../../components/Modal'
import { Button } from '../../components/Button'

/**
 * 保存時の409（版数の不一致）のダイアログ（開発Todo_スケジュール・ガントチャート_v1.1
 * D-07、12章補足8）。「最新を読み込む（編集内容は破棄）」と「編集を続ける」を選べる。
 * 入力中の内容は破棄せず画面に残す（D-07）ため、既定のエラートースト（`showApiError`）は
 * 出さず、呼び出し側（`useScheduleEditorState`）がこのダイアログの表示有無だけを管理する。
 */
export function ScheduleConflictDialog({
  open,
  onReload,
  onKeepEditing,
}: {
  open: boolean
  onReload: () => void
  onKeepEditing: () => void
}) {
  return (
    <Modal open={open} onClose={onKeepEditing} title={t('schedule.conflict.title')}>
      <p className="text-sm text-text-muted">{t('errors.SCHEDULE_REVISION_CONFLICT')}</p>
      <div className="mt-4 flex flex-col gap-2">
        <Button variant="primary" onClick={onReload}>
          {t('schedule.conflict.reload')}
        </Button>
        <Button variant="secondary" onClick={onKeepEditing}>
          {t('schedule.conflict.keepEditing')}
        </Button>
      </div>
    </Modal>
  )
}
