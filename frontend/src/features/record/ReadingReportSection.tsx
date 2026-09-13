import { t } from '../../locales/t'
import type { DailyRecordRead } from '../../api/records'
import type { ActiveReadingBook } from '../../api/goals'
import { CategoryReportSection } from './CategoryReportSection'
import { ReadingLogFields } from './ReadingLogFields'
import { ReadingLogSummaryList } from './ReadingLogSummaryList'
import { buildBookLabels } from './summaryLabels'
import { patchFormValue } from './formValues'
import type { CategoryActions } from './useDailyReportActions'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'

export type ReadingReportSectionProps = {
  record: DailyRecordRead
  /** ラベルの引き当て用の全書籍（表示対象の絞り込み前）。 */
  readingBooks: ActiveReadingBook[]
  targets: VisibleReportTargets
  draft: DailyReportDraft
  slotNames: Map<number, string>
  actions: CategoryActions
  isReported: boolean
}

/** 読書カテゴリの想起入力とAI対話・確定（仕様書6.5「読書目標の実績入力」、要件定義書R-65）。 */
export function ReadingReportSection({
  record,
  readingBooks,
  targets,
  draft,
  slotNames,
  actions,
  isReported,
}: ReadingReportSectionProps) {
  return (
    <CategoryReportSection
      labels={{
        title: t('dailyReport.readingLog.title'),
        chatTitle: t('dailyReport.readingChat.title'),
        chatStartLabel: t('dailyReport.readingChat.startButton'),
        finalizeLabel: t('dailyReport.readingLog.finalizeButton'),
      }}
      isReported={isReported}
      summary={
        <ReadingLogSummaryList
          readingLogs={record.reading_logs}
          bookLabels={buildBookLabels(readingBooks)}
        />
      }
      editor={
        <ReadingLogFields
          books={targets.books}
          values={draft.readingLogValues}
          slotNames={slotNames}
          onChangeField={(bookId, field, value) =>
            draft.setReadingLogValues((current) => patchFormValue(current, bookId, field, value))
          }
          onChangeSlotMinutes={(bookId, slotMinutes) =>
            draft.setReadingLogValues((current) =>
              patchFormValue(current, bookId, 'slotMinutes', slotMinutes),
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
