import { t } from '../../locales/t'
import type { DailyRecordRead } from '../../api/records'
import type { ActiveWorkAssignment } from '../../api/goals'
import { CategoryReportSection } from './CategoryReportSection'
import { WorkLogFields } from './WorkLogFields'
import { WorkLogSummaryList } from './WorkLogSummaryList'
import { buildWorkAssignmentLabels } from './summaryLabels'
import { patchFormValue } from './formValues'
import type { CategoryActions } from './useDailyReportActions'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'

export type WorkReportSectionProps = {
  record: DailyRecordRead
  /** ラベルの引き当て用の全案件（表示対象の絞り込み前）。 */
  workAssignments: ActiveWorkAssignment[]
  targets: VisibleReportTargets
  draft: DailyReportDraft
  actions: CategoryActions
  isReported: boolean
}

/** 仕事カテゴリの業務記録入力とAI対話・確定（仕様書6.5「仕事目標の実績入力」、要件定義書R-75）。
 * 資格試験・読書と異なり日次ノルマ・時間枠を持たないため、投下時間の入力欄はない。 */
export function WorkReportSection({
  record,
  workAssignments,
  targets,
  draft,
  actions,
  isReported,
}: WorkReportSectionProps) {
  return (
    <CategoryReportSection
      labels={{
        title: t('dailyReport.workLog.title'),
        chatTitle: t('dailyReport.workChat.title'),
        chatStartLabel: t('dailyReport.workChat.startButton'),
        finalizeLabel: t('dailyReport.workLog.finalizeButton'),
      }}
      isReported={isReported}
      summary={
        <WorkLogSummaryList
          workLogs={record.work_logs}
          workAssignmentLabels={buildWorkAssignmentLabels(workAssignments)}
        />
      }
      editor={
        <WorkLogFields
          workAssignments={targets.workAssignments}
          values={draft.workLogValues}
          onChangeField={(workAssignmentId, field, value) =>
            draft.setWorkLogValues((current) =>
              patchFormValue(current, workAssignmentId, field, value),
            )
          }
        />
      }
      messages={actions.messages}
      chat={actions.chat}
      finalize={actions.finalize}
    />
  )
}
