import { t } from '../../locales/t'
import type { DailyRecordRead } from '../../api/records'
import type { ActiveReadingBook } from '../../api/goals'
import { CategoryReportSection } from './CategoryReportSection'
import { ReadingLogFields } from './ReadingLogFields'
import { ReadingLogSummaryList } from './ReadingLogSummaryList'
import { RecordModeToggle } from './RecordModeToggle'
import { QuickRecordFields } from './QuickRecordFields'
import { buildBookLabels } from './summaryLabels'
import { patchFormValue } from './formValues'
import type { CategoryActions } from './useDailyReportActions'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'

export type ReadingReportSectionProps = {
  /** 「前回はこう書いていました」ヒントの取得に使う対象日。 */
  targetDate: string
  record: DailyRecordRead
  /** ラベルの引き当て用の全書籍（表示対象の絞り込み前）。 */
  readingBooks: ActiveReadingBook[]
  targets: VisibleReportTargets
  draft: DailyReportDraft
  slotNames: Map<number, string>
  actions: CategoryActions
  isReported: boolean
  /** 1行メモの最大文字数（`quick_record.note_max_chars`、開発Todo「ひとこと記録」v1.0）。 */
  quickNoteMaxChars: number
}

/** 読書カテゴリの想起入力とAI対話・確定（仕様書6.5「読書目標の実績入力」、要件定義書R-65）。
 *
 * ひとこと記録モード（開発Todo「ひとこと記録」v1.0 決定事項Q7）では、既存の想起質問欄も
 * 残したまま気分スタンプ＋1行メモを表示する。1行メモは最初の1冊の「自由に書く」欄
 * （freeText）へ書き込む（ExamReportSectionと同じ簡略化、通常は1冊のみ進行中のため）。 */
export function ReadingReportSection({
  targetDate,
  record,
  readingBooks,
  targets,
  draft,
  slotNames,
  actions,
  isReported,
  quickNoteMaxChars,
}: ReadingReportSectionProps) {
  // 呼び出し元（DailyReportPage）はtargets.showReadingSection（booksが1件以上あることが
  // 前提）のときのみ本コンポーネントを描画するため、booksが空になる分岐は到達しない
  // 防御的分岐（OPERATIONS.md「到達不能な防御的分岐」、WorkMemberSection.tsxと同じ方針）。
  /* v8 ignore next */
  const quickNoteBookId = targets.books[0]?.id ?? null
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
        <>
          <RecordModeToggle mode={draft.readingMode} onChange={draft.setReadingMode} />
          {/* v8 ignore next -- quickNoteBookIdがnullになる分岐は上記と同じ理由で到達しない */}
          {draft.readingMode === 'QUICK' && quickNoteBookId !== null && (
            <QuickRecordFields
              // readingLogValues[quickNoteBookId]も、useDailyReportDraftのhydrateが
              // 着手中の全書籍分を必ず作るため、quickNoteBookIdが着手中の書籍IDである限り
              // 未定義にはならない（同じ理由で到達しない防御的分岐）。
              /* v8 ignore next */
              note={draft.readingLogValues[quickNoteBookId]?.freeText ?? ''}
              onChangeNote={(value) =>
                draft.setReadingLogValues((current) =>
                  patchFormValue(current, quickNoteBookId, 'freeText', value),
                )
              }
              mood={draft.readingMood}
              onChangeMood={draft.setReadingMood}
              maxChars={quickNoteMaxChars}
              showNumbersSkippedNotice={false}
            />
          )}
          <ReadingLogFields
            targetDate={targetDate}
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
        </>
      }
      messages={actions.messages}
      chat={actions.chat}
      finalize={actions.finalize}
    />
  )
}
