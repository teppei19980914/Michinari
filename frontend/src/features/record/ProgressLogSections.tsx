import { t } from '../../locales/t'
import type { QuotaItemRead } from '../../api/records'
import { StudyLogFields } from './StudyLogFields'
import { ReadingLogFields } from './ReadingLogFields'
import { WorkLogFields } from './WorkLogFields'
import { patchFormValue } from './formValues'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { ProgressOnlyInput } from './resolveProgressOnlyInput'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'

export type ProgressLogSectionsProps = {
  /** 「前回はこう書いていました」ヒントの取得に使う対象日。 */
  targetDate: string
  /** 表示するセクション（確定済み・対象なしのカテゴリは除かれている）。 */
  input: ProgressOnlyInput
  /** 入力欄に並べる対象（教材・書籍・案件）。 */
  targets: VisibleReportTargets
  quotaItems: QuotaItemRead[]
  draft: DailyReportDraft
  slotNames: Map<number, string>
}

/** SC-07 進捗のみ登録のカテゴリ別入力欄（仕様書6.6「実績入力の構成は6.5と共通」）。
 *
 * 日次報告（SC-06）のCategoryReportSectionに相当するが、AI対話とカテゴリ別の確定を持たない
 * ため構成を共有していない（確定ボタンと対話カードの出し分けが、このカテゴリ分の入力欄には
 * 存在しない）。画面本体から切り出しているのは、1関数100行の上限を守るためである
 * （CODING_RULES.md「保守性（複雑度）」）。 */
export function ProgressLogSections({
  targetDate,
  input,
  targets,
  quotaItems,
  draft,
  slotNames,
}: ProgressLogSectionsProps) {
  return (
    <>
      {input.showExamSection && (
        <section className="flex flex-col gap-3">
          <h2 className="font-medium text-gray-900">{t('progressOnly.studyLog.title')}</h2>
          <StudyLogFields
            quotaItems={quotaItems}
            values={draft.studyLogValues}
            slotNames={slotNames}
            showMinutesOptionalNotice
            onChangeField={(materialId, field, value) =>
              draft.setStudyLogValues((current) => patchFormValue(current, materialId, field, value))
            }
            onChangeSlotMinutes={(materialId, slotMinutes) =>
              draft.setStudyLogValues((current) =>
                patchFormValue(current, materialId, 'slotMinutes', slotMinutes),
              )
            }
          />
        </section>
      )}

      {input.showReadingSection && (
        <section className="flex flex-col gap-3">
          <h2 className="font-medium text-gray-900">{t('progressOnly.readingLog.title')}</h2>
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
        </section>
      )}

      {input.showWorkSection && (
        <section className="flex flex-col gap-3">
          <h2 className="font-medium text-gray-900">{t('progressOnly.workLog.title')}</h2>
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
        </section>
      )}
    </>
  )
}
