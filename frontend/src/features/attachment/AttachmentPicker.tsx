/** 添付ファイルの複数選択UI（開発Todo_添付ファイル機能_v1.0 A1）。
 *
 * 日次報告・目標相談チャットの質問入力欄で共有する（A11、専用の採点テンプレート等は
 * 作らず既存の対話に選択UIを追加するだけで実現する方針）。選択状態は呼び出し側（画面）の
 * ローカルstateで保持し、DBへは永続化しない（P4）。 */
import { t } from '../../locales/t'
import { useAttachments } from './useAttachment'
import { totalSelectedChars } from './attachmentLogic'

export function AttachmentPicker({
  selectedIds,
  onChange,
}: {
  selectedIds: number[]
  onChange: (ids: number[]) => void
}) {
  const attachmentsQuery = useAttachments()
  const attachments = attachmentsQuery.data ?? []

  function toggle(id: number) {
    onChange(
      selectedIds.includes(id) ? selectedIds.filter((entry) => entry !== id) : [...selectedIds, id],
    )
  }

  if (attachments.length === 0) {
    return <p className="text-xs text-text-faint">{t('attachment.picker.none')}</p>
  }

  const totalChars = totalSelectedChars(attachments, selectedIds)

  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-text-muted">{t('attachment.picker.label')}</span>
      <ul className="flex flex-col gap-1">
        {attachments.map((attachment) => (
          <li key={attachment.id}>
            <label className="flex items-center gap-2 text-xs text-text-primary">
              <input
                type="checkbox"
                checked={selectedIds.includes(attachment.id)}
                onChange={() => toggle(attachment.id)}
              />
              <span className="truncate">{attachment.file_name}</span>
              <span className="shrink-0 text-text-faint">
                {t('attachment.charCountLabel', { count: attachment.char_count })}
              </span>
            </label>
          </li>
        ))}
      </ul>
      {selectedIds.length > 0 && (
        <span className="text-xs text-text-faint">
          {t('attachment.picker.selectedTotalChars', { count: totalChars })}
        </span>
      )}
    </div>
  )
}
