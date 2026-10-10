/** バックアップ一覧（SC-12 データ管理）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた DataManagementPage
 * から、一覧の表示だけを切り出したものである。復元は取り消せない操作のため、確認ダイアログ
 * とその実行は呼び出し元に残し、ここは押されたことを伝えるだけに徹する。 */
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { formatBytes } from './formatBytes'
import type { BackupRead } from '../../api/data'

export function BackupList({
  backups,
  isLoading,
  isRestoring,
  onRestore,
}: {
  backups: BackupRead[] | undefined
  isLoading: boolean
  isRestoring: boolean
  onRestore: (backupId: string) => void
}) {
  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-text-primary">{t('dataManagement.backups.title')}</h2>
      {isLoading && <p className="text-sm text-text-faint">{t('common.loading')}</p>}
      {backups && backups.length === 0 && (
        <p className="text-sm text-text-faint">{t('dataManagement.backups.empty')}</p>
      )}
      {backups && backups.length > 0 && (
        <ul className="flex flex-col gap-2">
          {backups.map((backup) => (
            <li
              key={backup.id}
              className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
            >
              <div>
                <p className="text-text-primary">
                  {t('dataManagement.backups.createdAtLabel')}:{' '}
                  {new Date(backup.created_at).toLocaleString()}
                </p>
                <p className="text-text-faint">
                  {t('dataManagement.backups.sizeLabel')}: {formatBytes(backup.size_bytes)}
                </p>
              </div>
              <Button
                variant="secondary"
                disabled={isRestoring}
                onClick={() => onRestore(backup.id)}
              >
                {t('dataManagement.backups.restore')}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
