/** AI評価レポートのレビュー・保存・ダウンロードカード（WorkEvaluationReportTab.tsxから
 * 切り出し、CODING_RULES.md「保守性（複雑度）」）。 */
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import { Button } from '../../components/Button'

export function WorkEvaluationReviewCard({
  body,
  onChangeBody,
  isSaving,
  onSave,
  onDownload,
}: {
  body: string
  onChangeBody: (value: string) => void
  isSaving: boolean
  onSave: () => void
  onDownload: () => void
}) {
  return (
    <Card className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.workEvaluationReport.bodyLabel')}
        <Textarea value={body} onChange={(e) => onChangeBody(e.target.value)} rows={12} />
      </label>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" disabled={isSaving} onClick={onSave}>
          {t('goals.workEvaluationReport.saveButton')}
        </Button>
        <Button variant="secondary" onClick={onDownload}>
          {t('goals.workEvaluationReport.downloadButton')}
        </Button>
      </div>
    </Card>
  )
}
