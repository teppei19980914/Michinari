/** AI評価レポートの生成履歴一覧（WorkEvaluationReportTab.tsxから切り出し、
 * CODING_RULES.md「保守性（複雑度）」）。クリックでレビューカードへ読み込む。 */
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { WorkEvaluationReportRead } from '../../api/closure'

export function WorkEvaluationHistoryList({
  reports,
  onSelect,
}: {
  reports: WorkEvaluationReportRead[]
  onSelect: (report: WorkEvaluationReportRead) => void
}) {
  return (
    <Card className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-gray-900">
        {t('goals.workEvaluationReport.historyTitle')}
      </h3>
      {reports.length === 0 && (
        <p className="text-sm text-gray-500">{t('goals.workEvaluationReport.historyEmpty')}</p>
      )}
      <ul className="flex flex-col gap-2">
        {reports.map((report) => (
          <li key={report.id}>
            <button
              type="button"
              className="w-full rounded-md border border-gray-200 p-2 text-left text-sm hover:bg-gray-50"
              onClick={() => onSelect(report)}
            >
              <span className="font-medium text-gray-900">{report.member_name}</span>
              <span className="ml-2 text-xs text-gray-500">{report.generated_at}</span>
              {report.edited_at && (
                <span className="ml-2 text-xs text-gray-400">
                  {t('goals.workEvaluationReport.editedBadge')}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}
