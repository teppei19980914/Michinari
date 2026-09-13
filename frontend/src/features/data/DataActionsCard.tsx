/** エクスポート・インポート・バックアップ作成の操作列（SC-12 データ管理）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた DataManagementPage
 * から切り出したものである。インポートは既存データを置き換える取り消せない操作のため、
 * 確認ダイアログと実行は呼び出し元に残し、ここはファイルが選ばれたことを伝えるだけにする。
 *
 * 選択後に入力欄の値を空へ戻すのはこの部品の責務とする。値が残っていると、同じファイルを
 * 選び直しても`change`が発火せず、2回目以降が無反応になる（ブラウザの挙動）。 */
import { useRef } from 'react'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'

export function DataActionsCard({
  isExporting,
  isImporting,
  isBackingUp,
  onExport,
  onPickImportFile,
  onBackup,
}: {
  isExporting: boolean
  isImporting: boolean
  isBackingUp: boolean
  onExport: () => void
  /** 利用者が選んだファイル。ダイアログを閉じただけの場合は呼ばれない。 */
  onPickImportFile: (file: File) => void
  onBackup: () => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  return (
    <Card className="flex flex-wrap gap-2">
      <Button variant="secondary" disabled={isExporting} onClick={onExport}>
        {t('dataManagement.export')}
      </Button>
      <Button
        variant="secondary"
        disabled={isImporting}
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
          onPickImportFile(file)
        }}
      />
      <Button variant="secondary" disabled={isBackingUp} onClick={onBackup}>
        {t('dataManagement.backup')}
      </Button>
    </Card>
  )
}
