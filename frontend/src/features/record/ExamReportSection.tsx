import { t } from '../../locales/t'
import type { DailyRecordRead, QuotaItemRead } from '../../api/records'
import { CategoryReportSection } from './CategoryReportSection'
import { StudyLogFields } from './StudyLogFields'
import { StudyLogSummaryList } from './StudyLogSummaryList'
import { DiaryFields } from './DiaryFields'
import { DiaryEntrySummaryList } from './DiaryEntrySummaryList'
import { RecordModeToggle } from './RecordModeToggle'
import { QuickRecordFields } from './QuickRecordFields'
import { buildMaterialLabels } from './summaryLabels'
import { filterWrittenDiaryEntries } from './diaryForm'
import { patchFormValue } from './formValues'
import type { CategoryActions } from './useDailyReportActions'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'

export type ExamReportSectionProps = {
  /** 「前回はこう書いていました」ヒントの取得に使う対象日。 */
  targetDate: string
  record: DailyRecordRead
  /** ラベルの引き当て用の全ノルマ（表示対象の絞り込み前）。 */
  quotaItems: QuotaItemRead[]
  targets: VisibleReportTargets
  draft: DailyReportDraft
  slotNames: Map<number, string>
  actions: CategoryActions
  isReported: boolean
  /** 1行メモの最大文字数（`quick_record.note_max_chars`、開発Todo「ひとこと記録」v1.0）。 */
  quickNoteMaxChars: number
}

/** 資格試験カテゴリの実績入力（学習実績＋日記）とAI対話・確定。
 * 日記を持つのは資格試験のみで、読書は想起（ReadingLogFields）が同じ役割を果たす。
 *
 * ひとこと記録モード（開発Todo「ひとこと記録」v1.0）では、学習実績入力（StudyLogFields）を
 * 表示せず気分スタンプ＋1行メモのみで確定できるようにする（決定事項Q1、`items=[]`の
 * 既存経路をそのまま使う）。1行メモは複数の目標が同時進行していても最初の1件の
 * `diaryLearned`へ書き込む（気分自体がgoal非依存の値のため、本モードでは1目標を前提とする
 * 簡略化。通常モードでは全目標分の日記欄をそのまま表示する）。 */
export function ExamReportSection({
  targetDate,
  record,
  quotaItems,
  targets,
  draft,
  slotNames,
  actions,
  isReported,
  quickNoteMaxChars,
}: ExamReportSectionProps) {
  const quickNoteGoalId = targets.diaryGoals[0]?.id ?? null
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
          <RecordModeToggle mode={draft.examMode} onChange={draft.setExamMode} />
          {draft.examMode === 'QUICK' && quickNoteGoalId !== null ? (
            <QuickRecordFields
              note={draft.diaryValues[quickNoteGoalId]?.diaryLearned ?? ''}
              onChangeNote={(value) =>
                draft.setDiaryValues((current) =>
                  patchFormValue(current, quickNoteGoalId, 'diaryLearned', value),
                )
              }
              mood={draft.examMood}
              onChangeMood={draft.setExamMood}
              maxChars={quickNoteMaxChars}
              showNumbersSkippedNotice
            />
          ) : (
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
                targetDate={targetDate}
                activeGoals={targets.diaryGoals}
                values={draft.diaryValues}
                onChangeLearned={(goalId, value) =>
                  draft.setDiaryValues((current) =>
                    patchFormValue(current, goalId, 'diaryLearned', value),
                  )
                }
              />
            </>
          )}
        </>
      }
      messages={actions.messages}
      chat={actions.chat}
      finalize={actions.finalize}
    />
  )
}
