/** ナレッジエクスポート（SC-13）の出力項目と匿名化の選択（仕様書6.10）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた KnowledgeExportPage
 * から切り出したものである。どの項目をどの呼び名で出すかの一覧は
 * exportSelectionItems.ts が持つ。 */
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { ExportSelection } from '../../api/export'
import type { GoalCategory } from '../../api/goals'
import { SELECTION_ITEMS } from './exportSelectionItems'

export function ExportSelectionCard({
  category,
  selection,
  onToggleField,
  anonymize,
  onChangeAnonymize,
}: {
  category: GoalCategory
  selection: ExportSelection
  onToggleField: (field: keyof ExportSelection, checked: boolean) => void
  anonymize: boolean
  onChangeAnonymize: (value: boolean) => void
}) {
  const isReading = category === 'READING'
  const isWork = category === 'WORK'
  const visibleItems = SELECTION_ITEMS.filter(
    (item) => !((isReading || isWork) && item.hiddenForReadingOrWork),
  )

  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-gray-900">{t('knowledgeExport.selection.title')}</h2>
      <div className="grid grid-cols-2 gap-1">
        {visibleItems.map((item) => {
          const labelKey = isWork
            ? (item.workLabelKey ?? item.labelKey)
            : isReading
              ? (item.readingLabelKey ?? item.labelKey)
              : item.labelKey
          return (
            <label key={item.field} className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={selection[item.field]}
                onChange={(e) => onToggleField(item.field, e.target.checked)}
              />
              {t(labelKey)}
            </label>
          )
        })}
      </div>
      <label className="mt-2 flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={anonymize}
          onChange={(e) => onChangeAnonymize(e.target.checked)}
        />
        {t('knowledgeExport.anonymize.label')}
      </label>
      <p className="text-xs text-gray-500">
        {t(
          isWork
            ? 'knowledgeExport.anonymize.workDescription'
            : isReading
              ? 'knowledgeExport.anonymize.readingDescription'
              : 'knowledgeExport.anonymize.description',
        )}
      </p>
    </Card>
  )
}
