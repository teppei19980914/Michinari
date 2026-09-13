import { t } from '../../locales/t'
import type { DailyRecordRead, QuotaItemRead } from '../../api/records'
import { CategoryReportSection } from './CategoryReportSection'
import { StudyLogFields } from './StudyLogFields'
import { StudyLogSummaryList } from './StudyLogSummaryList'
import { DiaryFields } from './DiaryFields'
import { DiaryEntrySummaryList } from './DiaryEntrySummaryList'
import { buildMaterialLabels } from './summaryLabels'
import { filterWrittenDiaryEntries } from './diaryForm'
import { patchFormValue } from './formValues'
import type { CategoryActions } from './useDailyReportActions'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'

export type ExamReportSectionProps = {
  record: DailyRecordRead
  /** ラベルの引き当て用の全ノルマ（表示対象の絞り込み前）。 */
  quotaItems: QuotaItemRead[]
  targets: VisibleReportTargets
  draft: DailyReportDraft
  slotNames: Map<number, string>
  actions: CategoryActions
  isReported: boolean
}

/** 資格試験カテゴリの実績入力（学習実績＋日記）とAI対話・確定。
 * 日記を持つのは資格試験のみで、読書は想起（ReadingLogFields）が同じ役割を果たす。 */
export function ExamReportSection({
  record,
  quotaItems,
  targets,
  draft,
  slotNames,
  actions,
  isReported,
}: ExamReportSectionProps) {
  return (
    <CategoryReportSection
      labels={{
        title: t('dailyReport.studyLog.title'),
        chatTitle: t('dailyReport.chat.title'),
        chatStartLabel: t('dailyReport.chat.startButton'),
        finalizeLabel: t('dailyReport.studyLog.finalizeButton'),
      }}
      isReported={isReported}
      summary={
        <>
          <StudyLogSummaryList
            studyLogs={record.study_logs}
            materialLabels={buildMaterialLabels(quotaItems)}
          />
          <DiaryEntrySummaryList diaryEntries={filterWrittenDiaryEntries(record.diary_entries)} />
        </>
      }
      editor={
        <>
          <StudyLogFields
            quotaItems={targets.quotaItems}
            values={draft.studyLogValues}
            slotNames={slotNames}
            onChangeField={(materialId, field, value) =>
              draft.setStudyLogValues((current) =>
                patchFormValue(current, materialId, field, value),
              )
            }
            onChangeSlotMinutes={(materialId, slotMinutes) =>
              draft.setStudyLogValues((current) =>
                patchFormValue(current, materialId, 'slotMinutes', slotMinutes),
              )
            }
          />
          <DiaryFields
            activeGoals={targets.diaryGoals}
            values={draft.diaryValues}
            onChangeField={(goalId, field, value) =>
              draft.setDiaryValues((current) => patchFormValue(current, goalId, field, value))
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
