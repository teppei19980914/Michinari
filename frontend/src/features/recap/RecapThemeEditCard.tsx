import { useState } from 'react'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import type { RecapThemeSummary } from '../../api/recap'

type RecapThemeEditCardProps = {
  themeName: string
  mergeCandidates: RecapThemeSummary[]
  isSaving: boolean
  onRename: (name: string) => void
  onMerge: (targetThemeId: number) => void
  onRebuild: () => void
}

/** テーマの改名・統合・再構築（仕様書6.1.3）。統合と再構築は確認を挟む（統合元は削除されるため）。 */
export function RecapThemeEditCard({
  themeName,
  mergeCandidates,
  isSaving,
  onRename,
  onMerge,
  onRebuild,
}: RecapThemeEditCardProps) {
  const [nameDraft, setNameDraft] = useState<string | null>(null)
  const [mergeTargetId, setMergeTargetId] = useState<number | ''>('')
  const currentName = nameDraft ?? themeName

  return (
    <Card className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('recapTheme.renameLabel')}
        <div className="flex gap-2">
          <Input
            value={currentName}
            onChange={(e) => setNameDraft(e.target.value)}
            className="flex-1"
          />
          <Button
            disabled={isSaving || currentName.trim() === '' || currentName === themeName}
            onClick={() => {
              onRename(currentName)
              setNameDraft(null)
            }}
          >
            {t('recapTheme.renameButton')}
          </Button>
        </div>
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('recapTheme.mergeLabel')}
        <div className="flex gap-2">
          <select
            className="flex-1 rounded-md border border-gray-300 p-2 text-sm"
            value={mergeTargetId}
            onChange={(e) => setMergeTargetId(e.target.value === '' ? '' : Number(e.target.value))}
          >
            <option value="">{t('recapTheme.mergePlaceholder')}</option>
            {mergeCandidates.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <Button
            variant="secondary"
            disabled={isSaving || mergeTargetId === ''}
            onClick={() => {
              if (mergeTargetId !== '' && window.confirm(t('recapTheme.mergeConfirm'))) {
                onMerge(mergeTargetId)
              }
            }}
          >
            {t('recapTheme.mergeButton')}
          </Button>
        </div>
      </label>
      <div className="flex justify-end">
        <Button
          variant="secondary"
          disabled={isSaving}
          onClick={() => {
            if (window.confirm(t('recapTheme.rebuildConfirm'))) {
              onRebuild()
            }
          }}
        >
          {t('recapTheme.rebuildButton')}
        </Button>
      </div>
    </Card>
  )
}
