import { t } from '../../locales/t'
import type { DailyRecordRead } from '../../api/records'
import type { ActiveWorkAssignment } from '../../api/goals'
import { CategoryReportSection } from './CategoryReportSection'
import { WorkLogFields } from './WorkLogFields'
import { WorkLogSummaryList } from './WorkLogSummaryList'
import { RecordModeToggle } from './RecordModeToggle'
import { QuickRecordFields } from './QuickRecordFields'
import { buildWorkAssignmentLabels } from './summaryLabels'
import { patchFormValue } from './formValues'
import type { CategoryActions } from './useDailyReportActions'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'

export type WorkReportSectionProps = {
  /** 「前回はこう書いていました」ヒントの取得に使う対象日。 */
  targetDate: string
  record: DailyRecordRead
  /** ラベルの引き当て用の全案件（表示対象の絞り込み前）。 */
  workAssignments: ActiveWorkAssignment[]
  targets: VisibleReportTargets
  draft: DailyReportDraft
  actions: CategoryActions
  isReported: boolean
  /** 1行メモの最大文字数（`quick_record.note_max_chars`、開発Todo「ひとこと記録」v1.0）。 */
  quickNoteMaxChars: number
}

/** 仕事カテゴリの業務記録入力とAI対話・確定（仕様書6.5「仕事目標の実績入力」、要件定義書R-75）。
 * 資格試験・読書と異なり日次ノルマ・時間枠を持たないため、投下時間の入力欄はない。
 *
 * ひとこと記録モード（開発Todo「ひとこと記録」v1.0 決定事項Q7）では、既存の質問欄も
 * 残したまま気分スタンプ＋1行メモを表示する。1行メモは最初の1案件の「自由に書く」欄
 * （freeText）へ書き込む（ReadingReportSectionと同じ簡略化）。 */
export function WorkReportSection({
  targetDate,
  record,
  workAssignments,
  targets,
  draft,
  actions,
  isReported,
  quickNoteMaxChars,
}: WorkReportSectionProps) {
  const quickNoteAssignmentId = targets.workAssignments[0]?.id ?? null
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
        <>
          <RecordModeToggle mode={draft.workMode} onChange={draft.setWorkMode} />
          {draft.workMode === 'QUICK' && quickNoteAssignmentId !== null && (
            <QuickRecordFields
              note={draft.workLogValues[quickNoteAssignmentId]?.freeText ?? ''}
              onChangeNote={(value) =>
                draft.setWorkLogValues((current) =>
                  patchFormValue(current, quickNoteAssignmentId, 'freeText', value),
                )
              }
              mood={draft.workMood}
              onChangeMood={draft.setWorkMood}
              maxChars={quickNoteMaxChars}
              showNumbersSkippedNotice={false}
            />
          )}
          <WorkLogFields
            targetDate={targetDate}
            workAssignments={targets.workAssignments}
            values={draft.workLogValues}
            onChangeField={(workAssignmentId, field, value) =>
              draft.setWorkLogValues((current) =>
                patchFormValue(current, workAssignmentId, field, value),
              )
            }
          />
        </>
      }
      messages={actions.messages}
      chat={actions.chat}
      finalize={actions.finalize}
    />
  )
}
