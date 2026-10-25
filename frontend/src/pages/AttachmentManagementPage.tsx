/** 添付ファイル管理画面（開発Todo_添付ファイル機能_v1.0 A9）。
 *
 * goal非依存の共通プールのため、目標一覧画面の近く（独立したページ）に配置し、
 * どの目標からも同じ一覧を選択できることをUI上でも表現する（A8・A9）。 */
import { useRef } from 'react'
import { t } from '../locales/t'
import { useToast } from '../components/toastContext'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { isAtMaxCount } from '../features/attachment/attachmentLogic'
import {
  useAttachmentLimits,
  useAttachments,
  useDeleteAttachment,
  useUploadAttachment,
} from '../features/attachment/useAttachment'

export function AttachmentManagementPage() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { showApiErrorWithTitle } = useToast()

  const attachmentsQuery = useAttachments()
  const limitsQuery = useAttachmentLimits()
  const uploadMutation = useUploadAttachment()
  const deleteMutation = useDeleteAttachment()

  const attachments = attachmentsQuery.data ?? []
  const atMaxCount =
    limitsQuery.data !== undefined && isAtMaxCount(attachments.length, limitsQuery.data.max_count)

  function handlePickFile(file: File) {
    uploadMutation.mutate(file, {
      onError: (error) => showApiErrorWithTitle(t('attachment.uploadButton'), error),
    })
  }

  function handleDelete(attachmentId: number) {
    if (!window.confirm(t('attachment.deleteConfirm'))) return
    deleteMutation.mutate(attachmentId, {
      onError: (error) => showApiErrorWithTitle(t('attachment.deleteButton'), error),
    })
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-text-primary">{t('attachment.pageTitle')}</h1>
      <p className="text-sm text-text-muted">{t('attachment.pageDescription')}</p>

      <Card className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            disabled={uploadMutation.isPending || atMaxCount}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploadMutation.isPending ? t('attachment.uploading') : t('attachment.uploadButton')}
          </Button>
          {atMaxCount && limitsQuery.data && (
            <span className="text-sm text-text-faint">
              {t('attachment.maxCountReached', { max: limitsQuery.data.max_count })}
            </span>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (!file) return
            handlePickFile(file)
          }}
        />

        {attachmentsQuery.isLoading && (
          <p className="text-sm text-text-faint">{t('common.loading')}</p>
        )}
        {attachmentsQuery.data && attachments.length === 0 && (
          <p className="text-sm text-text-faint">{t('attachment.emptyList')}</p>
        )}

        {attachments.length > 0 && (
          <ul className="flex flex-col divide-y divide-border">
            {attachments.map((attachment) => (
              <li
                key={attachment.id}
                className="flex items-center justify-between gap-2 py-2 text-sm"
              >
                <span className="truncate text-text-primary">{attachment.file_name}</span>
                <span className="shrink-0 text-text-faint">
                  {t('attachment.charCountLabel', { count: attachment.char_count })}
                </span>
                <Button
                  variant="secondary"
                  className="shrink-0"
                  disabled={deleteMutation.isPending}
                  onClick={() => handleDelete(attachment.id)}
                >
                  {t('attachment.deleteButton')}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
