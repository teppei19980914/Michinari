import { useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { useToast } from '../components/Toast'
import { createBackup, downloadExportFile, importDataFile, listBackups, restoreBackup } from '../api/data'
import { formatBytes } from '../features/data/formatBytes'

/** ブラウザへファイルをダウンロードさせる（GET /data/exportのJSON応答を
 * 受け取ったBlobをローカルファイルとして保存する、SC-12「エクスポート」）。 */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

/** SC-12 データ管理（仕様書6.12）。 */
export function DataManagementPage() {
  const queryClient = useQueryClient()
  const { showApiError, showToast } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const backupsQuery = useQuery({ queryKey: ['backups'], queryFn: listBackups })

  const exportMutation = useMutation({
    mutationFn: async () => {
      const blob = await downloadExportFile()
      downloadBlob(blob, 'michinari_export.json')
    },
    onSuccess: () => showToast(t('dataManagement.exportSucceeded')),
    onError: showApiError,
  })

  const importMutation = useMutation({
    mutationFn: (file: File) => importDataFile(file),
    onSuccess: () => {
      showToast(t('dataManagement.importSucceeded'))
      window.location.reload()
    },
    onError: showApiError,
  })

  const backupMutation = useMutation({
    mutationFn: createBackup,
    onSuccess: () => {
      showToast(t('dataManagement.backupSucceeded'))
      queryClient.invalidateQueries({ queryKey: ['backups'] })
    },
    onError: showApiError,
  })

  const restoreMutation = useMutation({
    mutationFn: (backupId: string) => restoreBackup(backupId),
    onSuccess: () => {
      showToast(t('dataManagement.backups.restoreSucceeded'))
      window.location.reload()
    },
    onError: showApiError,
  })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">{t('dataManagement.title')}</h1>

      <Card className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          disabled={exportMutation.isPending}
          onClick={() => exportMutation.mutate()}
        >
          {t('dataManagement.export')}
        </Button>
        <Button
          variant="secondary"
          disabled={importMutation.isPending}
          onClick={() => fileInputRef.current?.click()}
        >
          {t('dataManagement.import')}
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (!file) {
              return
            }
            if (window.confirm(t('dataManagement.importConfirm'))) {
              importMutation.mutate(file)
            }
          }}
        />
        <Button
          variant="secondary"
          disabled={backupMutation.isPending}
          onClick={() => backupMutation.mutate()}
        >
          {t('dataManagement.backup')}
        </Button>
      </Card>

      <Card className="flex flex-col gap-2">
        <h2 className="font-medium text-gray-900">{t('dataManagement.backups.title')}</h2>
        {backupsQuery.isLoading && <p className="text-sm text-gray-500">{t('common.loading')}</p>}
        {backupsQuery.data && backupsQuery.data.length === 0 && (
          <p className="text-sm text-gray-500">{t('dataManagement.backups.empty')}</p>
        )}
        {backupsQuery.data && backupsQuery.data.length > 0 && (
          <ul className="flex flex-col gap-2">
            {backupsQuery.data.map((backup) => (
              <li
                key={backup.id}
                className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2 text-sm"
              >
                <div>
                  <p className="text-gray-900">
                    {t('dataManagement.backups.createdAtLabel')}:{' '}
                    {new Date(backup.created_at).toLocaleString()}
                  </p>
                  <p className="text-gray-500">
                    {t('dataManagement.backups.sizeLabel')}: {formatBytes(backup.size_bytes)}
                  </p>
                </div>
                <Button
                  variant="secondary"
                  disabled={restoreMutation.isPending}
                  onClick={() => {
                    if (window.confirm(t('dataManagement.backups.restoreConfirm'))) {
                      restoreMutation.mutate(backup.id)
                    }
                  }}
                >
                  {t('dataManagement.backups.restore')}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
