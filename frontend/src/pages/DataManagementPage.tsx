import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { useToast } from '../components/Toast'
import { createBackup, downloadExportFile, importDataFile, listBackups, restoreBackup } from '../api/data'
import { BackupList } from '../features/data/BackupList'
import { DataActionsCard } from '../features/data/DataActionsCard'
import { downloadBlob } from '../utils/downloadBlob'
import { QUERY_KEYS } from '../constants/queryKeys'

/** SC-12 データ管理（仕様書6.12）。
 *
 * 操作列は DataActionsCard.tsx、バックアップ一覧は BackupList.tsx へ切り出してある
 * （CODING_RULES.md「保守性（複雑度）」）。取り消せない操作（インポート・復元）の確認
 * ダイアログはこの画面に残し、実行の可否をここで一元的に決める。 */
export function DataManagementPage() {
  const queryClient = useQueryClient()
  const { showApiError, showToast } = useToast()

  const backupsQuery = useQuery({ queryKey: QUERY_KEYS.backups(), queryFn: listBackups })

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
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.backups() })
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

      <DataActionsCard
        isExporting={exportMutation.isPending}
        isImporting={importMutation.isPending}
        isBackingUp={backupMutation.isPending}
        onExport={() => exportMutation.mutate()}
        onPickImportFile={(file) => {
          if (window.confirm(t('dataManagement.importConfirm'))) {
            importMutation.mutate(file)
          }
        }}
        onBackup={() => backupMutation.mutate()}
      />

      <BackupList
        backups={backupsQuery.data}
        isLoading={backupsQuery.isLoading}
        isRestoring={restoreMutation.isPending}
        onRestore={(backupId) => {
          if (window.confirm(t('dataManagement.backups.restoreConfirm'))) {
            restoreMutation.mutate(backupId)
          }
        }}
      />
    </div>
  )
}
