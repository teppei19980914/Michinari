import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { WorkLogRead } from '../../api/records'

export type WorkAssignmentLabel = { clientName: string | null }

/** 業務記録の読み取り専用表示（SC-08 日次報告閲覧、ReadingLogSummaryListの仕事版）。
 * 取引先名はGoalDetailRead.work_assignment経由で取得したものをlabels経由で受け取る。 */
export function WorkLogSummaryList({
  workLogs,
  workAssignmentLabels,
}: {
  workLogs: WorkLogRead[]
  workAssignmentLabels: Map<number, WorkAssignmentLabel>
}) {
  if (workLogs.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-2">
      {workLogs.map((log) => {
        const label = workAssignmentLabels.get(log.work_assignment_id)
        const title = label
          ? (label.clientName ?? t('dailyReport.workLog.noClientName'))
          : t('dailyReportView.workLog.unknownAssignment', { id: log.work_assignment_id })
        return (
          <Card key={log.id}>
            <p className="font-medium text-gray-900">{title}</p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-gray-900">{log.body}</p>
          </Card>
        )
      })}
    </div>
  )
}
